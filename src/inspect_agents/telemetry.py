"""Centralized telemetry service for tool event logging and redaction.

This module consolidates all telemetry-related concerns (logging, redaction,
profile enrichment, effective tool-output limit) into a single TelemetryService
abstraction, reducing change amplification when evolving telemetry schemas.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from typing import Any

from .settings import max_tool_output_env as _max_tool_output_env

# Local defaults (env-configurable)
_OBS_TRUNCATE = int(os.getenv("INSPECT_TOOL_OBS_TRUNCATE", "200"))


class TelemetryService:
    """Centralized service for tool event telemetry and observability.

    Responsibilities:
    - Log structured tool events with consistent formatting
    - Redact sensitive parameters from log payloads
    - Truncate large string fields for log efficiency
    - Emit one-time effective tool-output limit log
    - Provide extension points for profile enrichment
    """

    def __init__(self) -> None:
        """Initialize telemetry service with clean state."""
        self._effective_limit_logged = False
        self._logger = logging.getLogger("inspect_agents.tools")

    def redact_and_truncate(self, payload: dict[str, Any] | None, max_len: int | None = None) -> dict[str, Any]:
        """Redact sensitive keys and truncate large string fields.

        - Redaction uses approval.redact_arguments to apply the shared REDACT_KEYS policy.
        - Truncation applies to string values > max_len chars (default from env).
        """
        if not payload:
            return {}
        try:
            from .approval import redact_arguments
        except Exception:
            redacted = dict(payload)
        else:
            redacted = redact_arguments(dict(payload))  # type: ignore[arg-type]

        limit = max_len if (max_len is not None and max_len > 0) else _OBS_TRUNCATE

        def _truncate(v: Any) -> Any:
            try:
                if isinstance(v, str) and limit and len(v) > limit:
                    return v[:limit] + f"...[+{len(v) - limit} chars]"
                return v
            except Exception:
                return "[UNSERIALIZABLE]"

        return {k: _truncate(v) for k, v in redacted.items()}

    def maybe_emit_effective_tool_output_limit_log(self) -> None:
        """Emit a single structured log with the effective tool-output limit.

        Semantics preserved from observability module:
        - Reads optional env override `INSPECT_MAX_TOOL_OUTPUT` (bytes).
        - If set and upstream GenerateConfig has no explicit limit, set it once
          to keep precedence: explicit arg > GenerateConfig > env > fallback 16 KiB.
        - Logs a one-time `tool_event` with fields:
            { tool: "observability", phase: "info",
              effective_tool_output_limit: <int>, source: "env"|"default" }
        """
        if self._effective_limit_logged:
            return

        # Centralized accessor: returns None when unset/invalid; 0 allowed
        env_limit = _max_tool_output_env()

        source = "default"
        effective = 16 * 1024
        try:
            from inspect_ai.model._generate_config import (  # type: ignore
                active_generate_config,
                set_active_generate_config,
            )

            cfg = active_generate_config()
            # If env is provided and config has no explicit limit, adopt env
            if env_limit is not None and getattr(cfg, "max_tool_output", None) is None:
                try:
                    new_cfg = cfg.merge({"max_tool_output": env_limit})  # type: ignore[arg-type]
                    set_active_generate_config(new_cfg)
                except Exception:
                    try:
                        cfg.max_tool_output = env_limit  # type: ignore[attr-defined]
                    except Exception:
                        pass

            # Resolve effective limit
            cfg_limit = getattr(active_generate_config(), "max_tool_output", None)
            if cfg_limit is not None:
                effective = int(cfg_limit)
            elif env_limit is not None:
                effective = env_limit
            source = "env" if env_limit is not None else "default"
        except Exception:
            if env_limit is not None:
                effective = env_limit
                source = "env"

        try:
            payload = {
                "tool": "observability",
                "phase": "info",
                "effective_tool_output_limit": effective,
                "source": source,
            }
            self._logger.info("tool_event %s", json.dumps(payload, ensure_ascii=False))
        except Exception:
            self._logger.info(
                "tool_event %s",
                {
                    "tool": "observability",
                    "phase": "info",
                    "effective_tool_output_limit": effective,
                    "source": source,
                },
            )

        self._effective_limit_logged = True

    def get_effective_tool_output_limit(self) -> tuple[int, str]:
        """Return the effective tool-output limit and its source without side effects.

        Precedence mirrors the one-time log helper but performs no logging and
        makes no modifications to upstream config:
          1) Active GenerateConfig.max_tool_output → (value, "config")
          2) Env INSPECT_MAX_TOOL_OUTPUT → (value, "env")
          3) Fallback default 16 KiB → (16384, "default")
        """
        # Try config first (no side effects)
        try:
            from inspect_ai.model._generate_config import (  # type: ignore
                active_generate_config,
            )

            cfg = active_generate_config()
            cfg_limit = getattr(cfg, "max_tool_output", None)
            if cfg_limit is not None:
                try:
                    return int(cfg_limit), "config"
                except Exception:
                    # If malformed, fall through to env/default resolution
                    pass
        except Exception:
            # If upstream is unavailable, fall back to env/default
            pass

        # Next, environment
        env_limit = _max_tool_output_env()
        if env_limit is not None:
            return env_limit, "env"

        # Default (16 KiB)
        return 16 * 1024, "default"

    def log_tool_event(
        self,
        name: str,
        phase: str,
        args: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
        t0: float | None = None,
    ) -> float:
        """Emit a minimal structured log line for tool lifecycle.

        Returns a perf counter when phase == "start" so callers can pass it back
        on "end"/"error" to compute a duration.
        """
        # Defer one-time effective limit log until after the first real tool event
        # is logged, so timelines read naturally: event → cap log. Gate internal
        # diagnostics (e.g., "limits", "observability").
        _defer_cap_log = name not in {"limits", "observability"}

        now = time.perf_counter()
        data: dict[str, Any] = {
            "tool": name,
            "phase": phase,
        }
        if args:
            # Normalization policy: rewrite raw content fields to length metadata first
            try:
                norm = dict(args)
                mapping: list[tuple[str, str]] = [
                    ("content", "content_len"),
                    ("file_text", "file_text_len"),
                    ("old_string", "old_len"),
                    ("new_string", "new_len"),
                ]
                for src, dst in mapping:
                    if src in norm and isinstance(norm[src], str):
                        try:
                            norm[dst] = len(norm[src])
                        except Exception:
                            norm[dst] = "[len_error]"
                        norm.pop(src, None)
            except Exception:
                norm = args
            data["args"] = self.redact_and_truncate(norm)
        if t0 is not None and phase in ("end", "error"):
            try:
                data["duration_ms"] = round((now - t0) * 1000, 2)
            except Exception:
                pass
        if extra:
            for k, v in extra.items():
                if k not in data:
                    data[k] = v

        try:
            self._logger.info("tool_event %s", json.dumps(data, ensure_ascii=False))
        except Exception:
            self._logger.info("tool_event %s", {k: ("[obj]" if k == "args" else v) for k, v in data.items()})

        # Emit the cap log after logging the first real tool event
        if _defer_cap_log:
            self.maybe_emit_effective_tool_output_limit_log()

        return now if phase == "start" else (t0 or now)

    def log_agent_defaults_event(
        self,
        *,
        builder: str,
        include_defaults: bool,
        caller_supplied_tool_count: int,
        feature_flag_env: str = "INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS",
        feature_flag_state: str | None = None,
        include_defaults_source: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Emit telemetry for include_defaults usage on agent construction.

        Telemetry is best-effort; failures are swallowed to avoid impacting callers.
        """
        if feature_flag_state is None:
            try:
                flag_val = os.getenv(feature_flag_env)
            except Exception:
                flag_val = None
        else:
            flag_val = feature_flag_state

        payload: dict[str, Any] = {
            "builder": builder,
            "include_defaults": bool(include_defaults),
            "caller_supplied_tool_count": int(caller_supplied_tool_count),
            "caller_supplied_replacements": bool(caller_supplied_tool_count > 0),
            "feature_flag": feature_flag_env,
            "feature_flag_state": flag_val if flag_val is not None else "unset",
        }
        if include_defaults_source:
            payload.setdefault("include_defaults_source", include_defaults_source)
        if extra:
            for key, value in extra.items():
                payload.setdefault(key, value)

        try:
            self.log_tool_event(name="agent_defaults", phase="info", extra=payload)
        except Exception:
            pass

    def create_augmented_logger(
        self, augment_extra: Callable[[dict[str, Any] | None], dict[str, Any] | None]
    ) -> Callable[..., float]:
        """Create an augmented log_tool_event function with custom extra enrichment.

        This provides an extension point for components like FilesInstrumentation
        to inject profile context without duplicating core logging logic.

        Args:
            augment_extra: Function that takes optional extra dict and returns
                          augmented extra dict (or None)

        Returns:
            A log_tool_event function that applies augmentation before delegating
            to the core service implementation.
        """

        def augmented_log_tool_event(
            *,
            name: str,
            phase: str,
            args: dict[str, Any] | None = None,
            extra: dict[str, Any] | None = None,
            t0: float | None = None,
        ) -> float:
            """Augmented logger that enriches extra before delegating."""
            enriched_extra = augment_extra(extra)
            return self.log_tool_event(name=name, phase=phase, args=args, extra=enriched_extra, t0=t0)

        return augmented_log_tool_event


# Singleton instance for global use
_service = TelemetryService()


# Public API - delegate to singleton service
def log_tool_event(
    name: str,
    phase: str,
    args: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
    t0: float | None = None,
) -> float:
    """Emit a minimal structured log line for tool lifecycle."""
    return _service.log_tool_event(name=name, phase=phase, args=args, extra=extra, t0=t0)


def log_agent_defaults_event(
    *,
    builder: str,
    include_defaults: bool,
    caller_supplied_tool_count: int,
    feature_flag_env: str = "INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS",
    feature_flag_state: str | None = None,
    include_defaults_source: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit telemetry for include_defaults usage on agent construction."""
    return _service.log_agent_defaults_event(
        builder=builder,
        include_defaults=include_defaults,
        caller_supplied_tool_count=caller_supplied_tool_count,
        feature_flag_env=feature_flag_env,
        feature_flag_state=feature_flag_state,
        include_defaults_source=include_defaults_source,
        extra=extra,
    )


def maybe_emit_effective_tool_output_limit_log() -> None:
    """Emit a single structured log with the effective tool-output limit."""
    return _service.maybe_emit_effective_tool_output_limit_log()


def get_effective_tool_output_limit() -> tuple[int, str]:
    """Return the effective tool-output limit and its source without side effects."""
    return _service.get_effective_tool_output_limit()


def redact_and_truncate(payload: dict[str, Any] | None, max_len: int | None = None) -> dict[str, Any]:
    """Redact sensitive keys and truncate large string fields."""
    return _service.redact_and_truncate(payload, max_len)


def get_service() -> TelemetryService:
    """Get the singleton telemetry service instance.

    Useful for advanced use cases that need direct access to service methods
    or want to create augmented loggers.
    """
    return _service
