from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from .agents import build_subagents, build_supervisor
from .approval import approval_from_interrupt_config
from .model import resolve_model

# Limits (Inspect-AI)
try:  # Prefer real Inspect-AI if available
    from inspect_ai.util._limit import (
        Limit,
        message_limit,
        time_limit,
        token_limit,
    )
except Exception:  # pragma: no cover - tests may stub or omit upstream package
    # Create minimal shims to satisfy typing; actual behavior covered in integration
    class Limit:  # type: ignore
        pass

    def time_limit(value):  # type: ignore
        return value

    def message_limit(value):  # type: ignore
        return value

    def token_limit(value):  # type: ignore
        return value


class SupervisorCfg(BaseModel):
    prompt: str
    attempts: int | None = None
    truncation: Literal["auto", "disabled"] | None = None
    model: Any | None = None


class SubAgentCfg(BaseModel):
    name: str
    description: str
    prompt: str
    tools: list[str] | None = None
    model: Any | None = None
    # Optional role indirection; when provided (and model is absent),
    # resolved via `resolve_model(role=role)` to make YAML portable.
    role: str | None = None
    mode: Literal["handoff", "tool"] | None = None
    # Experimental quarantine controls (prefer explicit input_filter when set)
    context_scope: Literal["strict", "scoped"] | None = None
    include_state_summary: bool | None = None


class RootConfig(BaseModel):
    supervisor: SupervisorCfg
    subagents: list[SubAgentCfg] | None = Field(default=None)
    approvals: dict[str, Any] | None = Field(default=None)
    limits: list[Any] | None = Field(default=None)


def load_yaml(source: str | Path | dict[str, Any]) -> RootConfig:
    """Load YAML config from dict, file path, or inline YAML text.

    More robust path handling:
      - First tries the provided path (relative to cwd).
      - Then tries resolving relative to the repository root
        (first ancestor containing `pyproject.toml` or `.git`).
      - If no readable file is found, interprets `source` as inline YAML.

    Additionally validates that the parsed YAML root is a mapping
    before constructing `RootConfig`, producing a clear error otherwise.
    """

    # Fast-path: already a dict
    if isinstance(source, dict):
        data: dict[str, Any] = source
    else:
        resolved_path: Path | None = None
        src_path = Path(str(source))

        # 1) Try as-is (relative to current working directory)
        cand = src_path if src_path.is_absolute() else (Path.cwd() / src_path)
        if cand.exists():
            resolved_path = cand
        else:
            # 2) Try relative to a detected repo root
            here = Path(__file__).resolve()
            repo_root: Path | None = None
            for parent in [here] + list(here.parents):
                if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
                    repo_root = parent
                    break
            if repo_root is not None:
                alt = repo_root / src_path
                if alt.exists():
                    resolved_path = alt

        # Read text either from a resolved file path or treat as inline YAML
        if resolved_path is not None:
            text = resolved_path.read_text(encoding="utf-8")
        else:
            text = str(source)

        # Parse YAML safely and enforce mapping at the root
        try:
            loaded = yaml.safe_load(text)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid config YAML: {e}")

        if loaded is None:
            loaded = {}

        if not isinstance(loaded, dict):
            hint = f" at {resolved_path}" if resolved_path is not None else ""
            raise ValueError(f"Invalid config{hint}: expected a mapping at the root, got {type(loaded).__name__}")

        data = loaded

    try:
        return RootConfig(**data)
    except ValidationError as e:
        # Provide a concise message for tests/users
        raise ValueError(f"Invalid config: {e}")


def _limit_from_dict(spec: dict[str, Any]) -> Limit:
    """Map a minimal YAML spec into an Inspect limit object.

    Supported forms (minimal by design):
      - {type: "time"|"message"|"token", value: <number>}

    Convenience keys are also accepted:
      - time: {type: "time", seconds: <number>}
      - message: {type: "message", max: <int>}
      - token: {type: "token", max: <int>}
    """
    t = (spec.get("type") or spec.get("kind") or "").strip().lower()

    # Value resolution with a few forgiving aliases
    if t == "time":
        raw = spec.get("value", spec.get("seconds", spec.get("limit")))
        if raw is None or not isinstance(raw, (int, float)):
            raise ValueError("time limit requires numeric 'value' (seconds)")
        return time_limit(float(raw))
    elif t in ("message", "messages"):
        raw = spec.get("value", spec.get("max", spec.get("limit", spec.get("messages"))))
        if raw is not None and not isinstance(raw, int):
            raise ValueError("message limit requires integer 'value'")
        return message_limit(int(raw) if raw is not None else None)
    elif t in ("token", "tokens"):
        raw = spec.get("value", spec.get("max", spec.get("limit", spec.get("tokens"))))
        if raw is not None and not isinstance(raw, int):
            raise ValueError("token limit requires integer 'value'")
        return token_limit(int(raw) if raw is not None else None)
    else:
        raise ValueError(f"Unknown limit type: {t!r}")


def parse_limits(spec: list[Any] | None) -> list[Limit]:
    """Parse YAML limits into Inspect `Limit` objects.

    Ignores falsy/empty input; raises ValueError for malformed entries.
    """
    if not spec:
        return []
    limits: list[Limit] = []
    for i, entry in enumerate(spec):
        if isinstance(entry, dict):
            limits.append(_limit_from_dict(entry))
        else:
            raise ValueError(f"Invalid limit at index {i}: expected dict with 'type' and 'value'")
    return limits


def env_limits_for_agent(agent_name: str) -> list[Limit]:
    """Return Inspect `Limit` objects from per‑agent environment overrides.

    Reads the following variables after normalizing the agent name using
    `filters._normalize_agent_env_suffix(name)` (lowercase; non‑alphanumeric
    to `_`; collapsed underscores):

    - `INSPECT_LIMIT_TIME__<agent>`: seconds (float > 0)
    - `INSPECT_LIMIT_MESSAGES__<agent>`: max messages (int > 0)
    - `INSPECT_LIMIT_TOKENS__<agent>`: max tokens (int > 0)

    Returns a list of constructed Inspect `Limit` objects. Invalid, missing, or
    non‑positive values are ignored. This helper does not log; callers can
    emit diagnostics if desired.
    """
    try:
        # Import locally to avoid heavy deps and circular imports at module load
        from .filters import _normalize_agent_env_suffix  # type: ignore
    except Exception:
        return []

    suffix = _normalize_agent_env_suffix(agent_name)
    if not suffix:
        return []

    def _int_env(name: str) -> int | None:
        raw = os.getenv(name)
        if raw is None:
            return None
        try:
            val = int(str(raw).strip())
        except Exception:
            return None
        return val if val > 0 else None

    def _float_env(name: str) -> float | None:
        raw = os.getenv(name)
        if raw is None:
            return None
        try:
            val = float(str(raw).strip())
        except Exception:
            return None
        return val if val > 0 else None

    limits: list[Limit] = []

    t = _float_env(f"INSPECT_LIMIT_TIME__{suffix}")
    if t is not None:
        limits.append(time_limit(t))

    m = _int_env(f"INSPECT_LIMIT_MESSAGES__{suffix}")
    if m is not None:
        limits.append(message_limit(m))

    tk = _int_env(f"INSPECT_LIMIT_TOKENS__{suffix}")
    if tk is not None:
        limits.append(token_limit(tk))

    return limits


def build_from_config(
    cfg: RootConfig, *, model: Any | None = None
) -> tuple[object, list[object], list[Any], list[Limit]]:
    """Build a supervisor agent, tools, and approval policies from parsed config.

    Returns (agent, tools, approvals)
    """
    sub_tools: list[object] = []
    if cfg.subagents:
        # Build sub-agent tools using base tools (write_todos/fs) as universe
        from .tools import edit_file, ls, read_file, write_file, write_todos

        base_universe = [write_todos(), write_file(), read_file(), ls(), edit_file()]

        # Convert pydantic models to dicts expected by build_subagents
        sub_cfgs = [sa.model_dump(exclude_none=True) for sa in cfg.subagents]

        # Map experimental context_scope/include_state_summary to input_filter when provided
        # (explicit input_filter in config would still override)
        try:
            from inspect_agents.filters import (
                scoped_quarantine_filter,
                strict_quarantine_filter,
            )
        except Exception:
            strict_quarantine_filter = scoped_quarantine_filter = None  # type: ignore

        for sc in sub_cfgs:
            if "input_filter" in sc:
                continue  # explicit wins
            scope = sc.pop("context_scope", None)
            include_summary = sc.pop("include_state_summary", None)
            if scope == "strict" and callable(strict_quarantine_filter):
                sc["input_filter"] = strict_quarantine_filter()
            elif scope == "scoped" and callable(scoped_quarantine_filter):
                sc["input_filter"] = scoped_quarantine_filter(
                    include_state_summary=True if include_summary is None else bool(include_summary)
                )

        # Ensure each sub-agent has a model (fallback to a tiny echo agent)
        from inspect_ai.agent._agent import agent as as_agent

        @as_agent
        def _default_sub():
            async def execute(state, tools):
                from inspect_ai.model._chat_message import ChatMessageAssistant

                state.messages.append(ChatMessageAssistant(content="[subagent]"))
                return state

            return execute

        for sc in sub_cfgs:
            # If no explicit model but a role is provided, resolve it to a model
            # using the repository's role-aware resolver. Explicit model takes precedence.
            if "model" not in sc and "role" in sc and sc["role"]:
                sc["model"] = resolve_model(role=str(sc["role"]))
            # Remove role key to match expected schema for downstream builder
            sc.pop("role", None)
            # Ensure a model exists (fallback to a minimal echo sub-agent)
            sc.setdefault("model", _default_sub())

        sub_tools = build_subagents(
            configs=sub_cfgs,
            base_tools=base_universe,
        )

    # Resolve approvals
    approvals_cfg = cfg.approvals or {}
    approvals = approval_from_interrupt_config(approvals_cfg)

    # Parse runtime limits (optional)
    limits = parse_limits(cfg.limits)

    # Build supervisor
    sup = cfg.supervisor
    agent = build_supervisor(
        prompt=sup.prompt,
        tools=sub_tools,
        attempts=sup.attempts or 1,
        model=model or sup.model,
        truncation=sup.truncation or "disabled",
    )

    # Aggregate active tools (subtools only; supervisor already includes built-ins)
    active_tools = sub_tools

    return agent, active_tools, approvals, limits


def load_and_build(
    source: str | Path | dict[str, Any],
    *,
    model: Any | None = None,
) -> tuple[object, list[object], list[Any], list[Limit]]:
    return build_from_config(load_yaml(source), model=model)


__all__ = [
    "load_yaml",
    "build_from_config",
    "load_and_build",
    "parse_limits",
    "env_limits_for_agent",
    "RootConfig",
    "SupervisorCfg",
    "SubAgentCfg",
]
