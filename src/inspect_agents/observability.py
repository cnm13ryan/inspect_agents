# feat(observability): extract tool-event logging and one-time limit log
# Refactored to delegate to centralized TelemetryService

from __future__ import annotations

import os
from typing import Any

# Import the centralized telemetry service
from .telemetry import (
    get_effective_tool_output_limit as _get_effective_tool_output_limit,
)
from .telemetry import (
    log_agent_defaults_event as _log_agent_defaults_event,
)
from .telemetry import log_tool_event as _log_tool_event
from .telemetry import (
    maybe_emit_effective_tool_output_limit_log as _maybe_emit_effective_tool_output_limit_log,
)

# Public exports
__all__ = [
    "log_tool_event",
    "log_agent_defaults_event",
    "maybe_emit_effective_tool_output_limit_log",
    "get_effective_tool_output_limit",
]

# Local defaults (env-configurable) - kept for compatibility
_OBS_TRUNCATE = int(os.getenv("INSPECT_TOOL_OBS_TRUNCATE", "200"))

# One-time emission guard for effective tool-output limit log
# This is managed by TelemetryService, but we keep a placeholder here
# for backward compatibility. Tests that monkeypatch this attribute
# will need to also patch the service's _effective_limit_logged attribute.
_EFFECTIVE_LIMIT_LOGGED = False


def _parse_int(env_val: str | None) -> int | None:
    """Deprecated internal parser; kept for compatibility if needed.

    Prefer `settings.max_tool_output_env()` for INSPECT_MAX_TOOL_OUTPUT.
    """
    from .settings import max_tool_output_env

    return max_tool_output_env() if env_val else None


def maybe_emit_effective_tool_output_limit_log() -> None:
    """Emit a single structured log with the effective tool-output limit.

    Delegates to TelemetryService for actual implementation.
    """
    return _maybe_emit_effective_tool_output_limit_log()


def get_effective_tool_output_limit() -> tuple[int, str]:
    """Return the effective tool-output limit and its source without side effects.

    Delegates to TelemetryService for actual implementation.
    """
    return _get_effective_tool_output_limit()


def _redact_and_truncate(payload: dict[str, Any] | None, max_len: int | None = None) -> dict[str, Any]:
    """Redact sensitive keys and truncate large string fields.

    Delegates to TelemetryService for actual implementation.
    """
    from .telemetry import redact_and_truncate as _impl

    return _impl(payload, max_len)


def log_tool_event(
    name: str,
    phase: str,
    args: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
    t0: float | None = None,
) -> float:
    """Emit a minimal structured log line for tool lifecycle.

    Delegates to TelemetryService for actual implementation.
    """
    return _log_tool_event(name=name, phase=phase, args=args, extra=extra, t0=t0)


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
    """Emit telemetry for include_defaults usage on agent construction.

    Delegates to TelemetryService for actual implementation.
    """
    return _log_agent_defaults_event(
        builder=builder,
        include_defaults=include_defaults,
        caller_supplied_tool_count=caller_supplied_tool_count,
        feature_flag_env=feature_flag_env,
        feature_flag_state=feature_flag_state,
        include_defaults_source=include_defaults_source,
        extra=extra,
    )
