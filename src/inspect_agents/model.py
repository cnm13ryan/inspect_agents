from __future__ import annotations

# ruff: noqa: E402
"""Model resolver for Inspect-native agents.

Resolves a concrete Inspect model identifier or a role indirection string that
can be passed to `react(model=...)` or `get_model(...)`.

Rules (summary):
- Explicit `model` wins; return as-is if it contains a provider prefix ("/").
- If `role` is provided (and `model` is not), consult role → model env mapping
  and otherwise return "inspect/<role>".
- Prefer local (Ollama) by default: use `OLLAMA_MODEL_NAME` or a sensible default.
- If a remote provider is selected, fail fast when required API keys are absent.

Environment handling maintains legacy compatibility (deepagents-style) for the
two common local paths (Ollama, LM Studio) while returning Inspect-style model
strings (e.g., "ollama/<tag>", "openai-api/lm-studio/<model>").
"""

import logging
import os
from dataclasses import dataclass, field

LOCAL_DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL_NAME", "qwen3:4b-thinking-2507-q4_K_M")

# Module logger and one-time fallback guard
logger = logging.getLogger(__name__)
_OLLAMA_FALLBACK_WARNED = False

# Default roles known to the repository. These do not enforce a concrete model
# by default; in absence of env mapping they resolve to the Inspect role indirection
# string ("inspect/<role>") so that environments with Inspect-native role routing
# continue to work. Repositories may choose to add stricter defaults later.
DEFAULT_ROLES: tuple[str, ...] = (
    "researcher",
    "coder",
    "editor",
    "grader",
)


def _role_env_key(role: str) -> str:
    return f"INSPECT_ROLE_{role.upper().replace('-', '_')}"  # prefix; add _MODEL etc.


def _resolve_role_mapping(role: str) -> tuple[str | None, str | None]:
    """Resolve provider/model from role-specific env, if configured.

    Env precedence (if present):
    - INSPECT_ROLE_<ROLE>_MODEL: if value contains '/', interpret as
      '<provider-path>/<model-tag>' (e.g., 'openai-api/lm-studio/qwen3').
      Otherwise treat as a bare model tag to be combined with provider
      INSPECT_ROLE_<ROLE>_PROVIDER or default provider resolution.

    Returns:
        (provider, model) or (None, None) if no mapping is configured.
    """

    base = _role_env_key(role)
    raw = os.getenv(f"{base}_MODEL")
    if not raw:
        _log_role_mapping_debug(role, base, None, None, None, None, "no_model_env")
        return (None, None)

    raw = raw.strip()
    if "/" in raw:
        # Split '<provider-path>/<tag>' while allowing provider paths that contain '/'
        *provider_parts, tag = raw.split("/")
        provider = "/".join(provider_parts)
        _log_role_mapping_debug(role, base, raw, provider, tag, None, "provider_in_model")
        return (provider, tag)

    # Bare model tag; find provider override or fall back to default chain
    provider_env = os.getenv(f"{base}_PROVIDER")
    provider = None
    if provider_env:
        provider = provider_env.strip().lower()
    _log_role_mapping_debug(role, base, raw, provider, raw, provider_env, "bare_model_tag")
    return (provider, raw)


# ---------- Explain API: typed trace & error ----------


@dataclass(slots=True)
class ModelResolutionStep:
    """One step in model resolution with key inputs and an optional candidate.

    Fields mirror `_log_model_debug` payload for structured introspection.
    """

    path: str
    provider_arg: str | None
    model_arg: str | None
    role: str | None
    role_env_model: str | None
    role_env_provider: str | None
    env_inspect_eval_model: str | None
    final_candidate: str | None = None


@dataclass(slots=True)
class ModelResolutionTrace:
    """Full trace of resolution steps and the final string.

    Added fields:
    - env_inspect_eval_model_raw: normalized raw value of INSPECT_EVAL_MODEL (lowercased, stripped),
      when present. Useful for detecting the sentinel "none/none" explicitly.
    - inspect_eval_disabled: True when INSPECT_EVAL_MODEL is set to the sentinel "none/none".
    """

    steps: list[ModelResolutionStep] = field(default_factory=list)
    final: str | None = None
    env_inspect_eval_model_raw: str | None = None
    inspect_eval_disabled: bool = False
    provider_source: str | None = None  # arg|env|role-map|inspect-eval|default
    model_source: str | None = None  # arg|env|role-map|inspect-eval|default
    role_source: str | None = None  # arg|unset
    inspect_eval_source: str = "unset"  # unset|sentinel|set


class ResolveModelError(RuntimeError):
    """Typed error carrying the resolution trace for programmatic use."""

    def __init__(self, message: str, final_step: ModelResolutionStep, trace: ModelResolutionTrace):
        super().__init__(message)
        self.final_step: ModelResolutionStep = final_step
        self.trace: ModelResolutionTrace = trace


def _step(
    *,
    path: str,
    provider_arg: str | None,
    model_arg: str | None,
    role: str | None,
    role_env_model: str | None,
    role_env_provider: str | None,
    env_inspect_eval_model: str | None,
    final_candidate: str | None = None,
) -> ModelResolutionStep:
    return ModelResolutionStep(
        path=path,
        provider_arg=provider_arg,
        model_arg=model_arg,
        role=role,
        role_env_model=role_env_model,
        role_env_provider=role_env_provider,
        env_inspect_eval_model=env_inspect_eval_model,
        final_candidate=final_candidate,
    )


def resolve_model_explain(
    provider: str | None = None,
    model: str | None = None,
    role: str | None = None,
) -> tuple[str, ModelResolutionTrace]:
    """Resolve model and return a structured trace alongside the final string.

    This mirrors `resolve_model(...)` semantics without changing them. Errors
    are raised as `ResolveModelError` with an attached trace.
    """

    trace = ModelResolutionTrace()
    provider_arg = provider
    model_arg = model
    role_env_model: str | None = None
    role_env_provider: str | None = None

    # Record role source when provided
    if role is not None:
        trace.role_source = "arg"

    # 1) Explicit model with provider prefix wins
    if model and "/" in model:
        step = _step(
            path="explicit_model_with_provider",
            provider_arg=provider_arg,
            model_arg=model_arg,
            role=role,
            role_env_model=None,
            role_env_provider=None,
            env_inspect_eval_model=os.getenv("INSPECT_EVAL_MODEL"),
            final_candidate=model,
        )
        trace.steps.append(step)
        trace.final = model
        trace.model_source = "arg"
        try:
            prov = model.split("/", 1)[0]
            if prov:
                trace.provider_source = trace.provider_source or "arg"
        except Exception:
            pass
        return model, trace

    # 2) Role-mapped resolution when role is provided and no explicit model
    if model is None and role:
        r_provider, r_model = _resolve_role_mapping(role)
        role_env_provider = r_provider
        role_env_model = r_model
        if r_provider or r_model:
            # Stash mapping and continue down provider chain
            step = _step(
                path="role_env_mapping",
                provider_arg=provider_arg,
                model_arg=model_arg,
                role=role,
                role_env_model=role_env_model,
                role_env_provider=role_env_provider,
                env_inspect_eval_model=os.getenv("INSPECT_EVAL_MODEL"),
            )
            trace.steps.append(step)
            provider = r_provider or provider
            model = r_model
            if r_provider:
                trace.provider_source = "role-map"
            if r_model:
                trace.model_source = "role-map"
        else:
            final = f"inspect/{role}"
            step = _step(
                path="role_inspect_indirection",
                provider_arg=provider_arg,
                model_arg=model_arg,
                role=role,
                role_env_model=None,
                role_env_provider=None,
                env_inspect_eval_model=os.getenv("INSPECT_EVAL_MODEL"),
                final_candidate=final,
            )
            trace.steps.append(step)
            trace.final = final
            return final, trace

    # 3) Env-specified full model via Inspect convention
    env_inspect_model = os.getenv("INSPECT_EVAL_MODEL")
    try:
        if env_inspect_model is not None:
            norm_env = env_inspect_model.strip().lower()
            trace.env_inspect_eval_model_raw = norm_env
            if norm_env == "none/none":
                trace.inspect_eval_disabled = True
                trace.inspect_eval_source = "sentinel"
            else:
                trace.inspect_eval_source = "set"
    except Exception:
        pass
    if (
        model is None
        and env_inspect_model
        and "/" in env_inspect_model
        and env_inspect_model.strip().lower() != "none/none"
    ):
        step = _step(
            path="env_INSPECT_EVAL_MODEL",
            provider_arg=provider_arg,
            model_arg=model_arg,
            role=role,
            role_env_model=role_env_model,
            role_env_provider=role_env_provider,
            env_inspect_eval_model=env_inspect_model,
            final_candidate=env_inspect_model,
        )
        trace.steps.append(step)
        trace.final = env_inspect_model
        trace.provider_source = "inspect-eval"
        trace.model_source = "inspect-eval"
        return env_inspect_model, trace

    # 4) Determine provider: function arg > env > default (ollama)
    if provider is not None:
        trace.provider_source = trace.provider_source or "arg"
        provider = provider.lower()
    else:
        env_provider = os.getenv("DEEPAGENTS_MODEL_PROVIDER")
        provider = (env_provider or "ollama").lower()
        if env_provider:
            trace.provider_source = trace.provider_source or "env"
        else:
            trace.provider_source = trace.provider_source or "default"

    # 5) Provider-specific resolution
    if provider in {"ollama"}:
        tag_env = os.getenv("OLLAMA_MODEL_NAME")
        tag = model or tag_env or LOCAL_DEFAULT_OLLAMA_MODEL
        final = f"ollama/{tag}"
        step = _step(
            path="provider_ollama",
            provider_arg=provider_arg,
            model_arg=model_arg,
            role=role,
            role_env_model=role_env_model,
            role_env_provider=role_env_provider,
            env_inspect_eval_model=env_inspect_model,
            final_candidate=final,
        )
        trace.steps.append(step)
        trace.final = final
        if model is not None:
            trace.model_source = trace.model_source or "arg"
        else:
            trace.model_source = trace.model_source or ("env" if tag_env else "default")
        return final, trace

    if provider in {"lm-studio", "lmstudio"}:
        tag = model or os.getenv("LM_STUDIO_MODEL_NAME") or "local-model"
        final = f"openai-api/lm-studio/{tag}"
        step = _step(
            path="provider_lm_studio",
            provider_arg=provider_arg,
            model_arg=model_arg,
            role=role,
            role_env_model=role_env_model,
            role_env_provider=role_env_provider,
            env_inspect_eval_model=env_inspect_model,
            final_candidate=final,
        )
        trace.steps.append(step)
        trace.final = final
        trace.model_source = trace.model_source or "arg"
        return final, trace

    remote_requires = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "perplexity": "PERPLEXITY_API_KEY",
        "fireworks": "FIREWORKS_API_KEY",
        "grok": "GROK_API_KEY",
        "goodfire": "GOODFIRE_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }

    if provider in remote_requires:
        key_var = remote_requires[provider]
        step_base = _step(
            path=f"provider_{provider}",
            provider_arg=provider_arg,
            model_arg=model_arg,
            role=role,
            role_env_model=role_env_model,
            role_env_provider=role_env_provider,
            env_inspect_eval_model=env_inspect_model,
        )
        if not os.getenv(key_var):
            trace.steps.append(step_base)
            raise ResolveModelError(
                f"Provider '{provider}' requires {key_var} to be set.",
                final_step=step_base,
                trace=trace,
            )
        env_tag = os.getenv(f"{provider.upper()}_MODEL")
        tag = model or env_tag
        if not tag:
            trace.steps.append(step_base)
            raise ResolveModelError(
                (
                    f"Model not specified for provider '{provider}'. Set the 'model' argument "
                    f"or {provider.upper()}_MODEL environment variable."
                ),
                final_step=step_base,
                trace=trace,
            )
        final = f"{provider}/{tag}"
        step = step_base
        step.final_candidate = final
        trace.steps.append(step)
        trace.final = final
        trace.model_source = trace.model_source or ("arg" if model is not None else "env")
        return final, trace

    if provider.startswith("openai-api/"):
        _, vendor = provider.split("/", 1)
        env_prefix = vendor.upper().replace("-", "_")
        key_var = f"{env_prefix}_API_KEY"
        step_base = _step(
            path=f"provider_openai_api_{vendor}",
            provider_arg=provider_arg,
            model_arg=model_arg,
            role=role,
            role_env_model=role_env_model,
            role_env_provider=role_env_provider,
            env_inspect_eval_model=env_inspect_model,
        )
        if not os.getenv(key_var):
            trace.steps.append(step_base)
            raise ResolveModelError(
                f"Provider '{provider}' requires {key_var} to be set.",
                final_step=step_base,
                trace=trace,
            )
        env_tag = os.getenv(f"{env_prefix}_MODEL")
        tag = model or env_tag
        if not tag:
            trace.steps.append(step_base)
            raise ResolveModelError(
                (
                    f"Model not specified for provider '{provider}'. Set the 'model' argument "
                    f"or {env_prefix}_MODEL environment variable."
                ),
                final_step=step_base,
                trace=trace,
            )
        final = f"openai-api/{vendor}/{tag}"
        step = step_base
        step.final_candidate = final
        trace.steps.append(step)
        trace.final = final
        trace.model_source = trace.model_source or ("arg" if model is not None else "env")
        return final, trace

    # Fallback: if model provided without slash (no provider), assume provider prefix
    if model:
        final = f"{provider}/{model}"
        step = _step(
            path="fallback_model_with_provider",
            provider_arg=provider_arg,
            model_arg=model_arg,
            role=role,
            role_env_model=role_env_model,
            role_env_provider=role_env_provider,
            env_inspect_eval_model=env_inspect_model,
            final_candidate=final,
        )
        trace.steps.append(step)
        trace.final = final
        return final, trace

    # Final fallback: prefer Ollama
    final = f"ollama/{LOCAL_DEFAULT_OLLAMA_MODEL}"
    step = _step(
        path="final_fallback_ollama",
        provider_arg=provider_arg,
        model_arg=model_arg,
        role=role,
        role_env_model=role_env_model,
        role_env_provider=role_env_provider,
        env_inspect_eval_model=env_inspect_model,
        final_candidate=final,
    )
    trace.steps.append(step)
    trace.final = final
    trace.model_source = trace.model_source or ("env" if os.getenv("OLLAMA_MODEL_NAME") else "default")
    return final, trace


def resolve_model(
    provider: str | None = None,
    model: str | None = None,
    role: str | None = None,
) -> str:
    """Resolve an Inspect model identifier or a role mapping.

    Args:
        provider: Preferred provider (e.g., "ollama", "lm-studio", "openai").
        model: Explicit model (with or without provider prefix). If it contains
            a provider prefix ("/"), it is returned as-is.
        role: Model role indirection (returns "inspect/<role>" when provided
            and no explicit model is given).

    Returns:
        A model string acceptable to Inspect (e.g., "ollama/llama3.1",
        "openai/gpt-4o-mini", "openai-api/lm-studio/qwen3", or
        "inspect/<role>").

    Raises:
        RuntimeError: if a remote provider is selected without required keys.
    """

    try:
        final, trace = resolve_model_explain(provider=provider, model=model, role=role)
    except ResolveModelError as err:
        # Preserve previous external behavior (RuntimeError + message)
        raise RuntimeError(str(err))

    # One-time operator hint for implicit local fallback
    last_path = trace.steps[-1].path if trace.steps else None
    if last_path == "final_fallback_ollama":
        global _OLLAMA_FALLBACK_WARNED
        if not _OLLAMA_FALLBACK_WARNED:
            logger.info(
                "Model resolver: %s -> using %s because no provider/model/role mapping was set. "
                "To avoid implicit local fallback, set INSPECT_EVAL_MODEL or configure a provider via "
                "DEEPAGENTS_MODEL_PROVIDER and <PROVIDER>_MODEL (e.g., OPENAI_MODEL).",
                last_path,
                final,
            )
            _OLLAMA_FALLBACK_WARNED = True

    # Emit debug log mirroring previous payload (best-effort)
    # Use the last step to populate fields
    if trace.steps:
        s = trace.steps[-1]
        _log_model_debug(
            role=role,
            provider_arg=s.provider_arg,
            model_arg=s.model_arg,
            role_env_model=s.role_env_model,
            role_env_provider=s.role_env_provider,
            env_inspect_eval_model=s.env_inspect_eval_model,
            final=final,
            path=s.path,
        )

    return final


def _log_model_debug(
    role: str | None,
    provider_arg: str | None,
    model_arg: str | None,
    role_env_model: str | None,
    role_env_provider: str | None,
    env_inspect_eval_model: str | None,
    final: str,
    path: str,
) -> None:
    """Log model resolution debug information when INSPECT_MODEL_DEBUG is set."""
    if not os.getenv("INSPECT_MODEL_DEBUG"):
        return

    logger = logging.getLogger(__name__)
    logger.info(
        "Model resolution: role=%s provider_arg=%s model_arg=%s "
        "role_env_model=%s role_env_provider=%s env_inspect_eval_model=%s "
        "final=%s path=%s",
        role,
        provider_arg,
        model_arg,
        role_env_model,
        role_env_provider,
        env_inspect_eval_model,
        final,
        path,
    )


def _log_role_mapping_debug(
    role: str,
    base: str,
    raw: str | None,
    provider: str | None,
    model: str | None,
    provider_env: str | None,
    path: str,
) -> None:
    """Log role mapping resolution debug information when INSPECT_MODEL_DEBUG is set."""
    if not os.getenv("INSPECT_MODEL_DEBUG"):
        return

    logger = logging.getLogger(__name__)
    logger.info(
        "Role mapping resolution: role=%s base=%s raw=%s provider=%s model=%s provider_env=%s path=%s",
        role,
        base,
        raw,
        provider,
        model,
        provider_env,
        path,
    )
