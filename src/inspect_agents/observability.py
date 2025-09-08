# feat(observability): extract tool-event logging and one-time limit log

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from .settings import max_tool_output_env as _max_tool_output_env

# Public exports
__all__ = [
    "log_tool_event",
    "maybe_emit_effective_tool_output_limit_log",
    "get_effective_tool_output_limit",
]

# Local defaults (env-configurable)
_OBS_TRUNCATE = int(os.getenv("INSPECT_TOOL_OBS_TRUNCATE", "200"))

# One-time emission guard for effective tool-output limit log
_EFFECTIVE_LIMIT_LOGGED = False


def _parse_int(env_val: str | None) -> int | None:
    """Deprecated internal parser; kept for compatibility if needed.

    Prefer `settings.max_tool_output_env()` for INSPECT_MAX_TOOL_OUTPUT.
    """
    try:
        if env_val is None:
            return None
        val = int(env_val.strip())
        if val < 0:
            return None
        return val
    except Exception:
        return None


def maybe_emit_effective_tool_output_limit_log() -> None:
    """Emit a single structured log with the effective tool-output limit.

    Semantics preserved from tools._maybe_emit_effective_tool_output_limit_log:
    - Reads optional env override `INSPECT_MAX_TOOL_OUTPUT` (bytes).
    - If set and upstream GenerateConfig has no explicit limit, set it once
      to keep precedence: explicit arg > GenerateConfig > env > fallback 16 KiB.
    - Logs a one-time `tool_event` with fields:
        { tool: "observability", phase: "info",
          effective_tool_output_limit: <int>, source: "env"|"default" }
    - One-time behavior is coordinated entirely within this module to avoid
      cross-module import coupling with tools.
    """
    global _EFFECTIVE_LIMIT_LOGGED
    if _EFFECTIVE_LIMIT_LOGGED:
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

    # Use the historical logger name for compatibility
    logger = logging.getLogger("inspect_agents.tools")
    try:
        payload = {
            "tool": "observability",
            "phase": "info",
            "effective_tool_output_limit": effective,
            "source": source,
        }
        logger.info("tool_event %s", json.dumps(payload, ensure_ascii=False))
    except Exception:
        logger.info(
            "tool_event %s",
            {"tool": "observability", "phase": "info", "effective_tool_output_limit": effective, "source": source},
        )

    # Mark as logged within this module only
    _EFFECTIVE_LIMIT_LOGGED = True


def get_effective_tool_output_limit() -> tuple[int, str]:
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


def _redact_and_truncate(payload: dict[str, Any] | None, max_len: int | None = None) -> dict[str, Any]:
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


def log_tool_event(
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

    logger = logging.getLogger("inspect_agents.tools")  # preserve logger name
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
        data["args"] = _redact_and_truncate(norm)
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
        logger.info("tool_event %s", json.dumps(data, ensure_ascii=False))
    except Exception:
        logger.info("tool_event %s", {k: ("[obj]" if k == "args" else v) for k, v in data.items()})

    # Emit the cap log after logging the first real tool event
    if _defer_cap_log:
        maybe_emit_effective_tool_output_limit_log()

    return now if phase == "start" else (t0 or now)
