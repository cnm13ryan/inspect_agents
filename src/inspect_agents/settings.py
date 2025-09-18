"""Centralized environment/settings utilities for inspect_agents.

Semantics mirror existing helpers to avoid regressions:
- truthy: case-insensitive membership in {"1","true","yes","on"}.
- default_tool_timeout: float from INSPECT_AGENTS_TOOL_TIMEOUT (fallback 15.0).
- typed_results_enabled: truthy(INSPECT_AGENTS_TYPED_RESULTS).
- int_env: parse int with optional min/max clamping; default on errors.
- float_env: parse float; default on errors.
- str_env: passthrough string (or default/None when unset).
"""

from __future__ import annotations

import os


def truthy(val: str | None) -> bool:
    """Return True for common truthy string values.

    Accepts: "1", "true", "yes", "on" (case-insensitive). None -> False.
    """
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


def int_env(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    """Read an integer env var with optional clamping and safe fallback.

    - Returns `default` on parse errors or when unset.
    - Applies `minimum`/`maximum` clamps when provided.
    """
    raw = os.getenv(name)
    try:
        val = int(raw) if raw is not None and str(raw).strip() != "" else int(default)
    except Exception:
        val = int(default)
    if minimum is not None:
        val = max(minimum, val)
    if maximum is not None:
        val = min(maximum, val)
    return val


def float_env(name: str, default: float) -> float:
    """Read a float env var; return `default` on errors or when unset."""
    raw = os.getenv(name)
    try:
        return float(raw) if raw is not None and str(raw).strip() != "" else float(default)
    except Exception:
        return float(default)


def str_env(name: str, default: str | None = None) -> str | None:
    """Read a string env var; return `default` when unset."""
    val = os.getenv(name)
    return default if val is None else val


def max_tool_output_env() -> int | None:
    """Parse `INSPECT_MAX_TOOL_OUTPUT` as a non-negative int.

    Returns None when the variable is unset or invalid. Value ``0`` is allowed
    and indicates truncation is disabled.
    """
    import os as _os

    raw = _os.getenv("INSPECT_MAX_TOOL_OUTPUT")
    try:
        if raw is None or str(raw).strip() == "":
            return None
        val = int(str(raw).strip())
        return val if val >= 0 else None
    except Exception:
        return None


def typed_results_enabled() -> bool:
    """Whether typed result models should be returned by tools."""
    return truthy(os.getenv("INSPECT_AGENTS_TYPED_RESULTS"))


def default_tool_timeout() -> float:
    """Default tool timeout (seconds). Env: INSPECT_AGENTS_TOOL_TIMEOUT (float)."""
    return float_env("INSPECT_AGENTS_TOOL_TIMEOUT", 15.0)


_FALSEY = {"0", "false", "no", "off"}
_FEATURE_FLAG_INCLUDE_DEFAULTS = "INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS"


def include_defaults_env() -> tuple[bool | None, str | None]:
    """Return (bool, raw) for the include-defaults feature flag.

    - True/False when the environment specifies an explicit toggle.
    - (None, raw) when unset or invalid so callers can fall back to defaults
      while still surfacing the provided text in telemetry.
    """

    raw = os.getenv(_FEATURE_FLAG_INCLUDE_DEFAULTS)
    if raw is None:
        return None, None

    value = raw.strip()
    if value == "":
        return None, raw

    lowered = value.lower()
    if truthy(lowered):
        return True, raw
    if lowered in _FALSEY:
        return False, raw
    return None, raw


def resolve_include_defaults(explicit: bool | None) -> tuple[bool, str, str | None]:
    """Resolve include-defaults preference with env override semantics.

    Returns a tuple of `(include_defaults, source, env_raw)` where `source` is
    one of "explicit", "env", or "default". Defaults to True when neither an
    explicit argument nor an env override is provided.
    """

    env_value, env_raw = include_defaults_env()
    if explicit is not None:
        return bool(explicit), "explicit", env_raw
    if env_value is not None:
        return env_value, "env", env_raw
    return True, "default", env_raw


__all__ = [
    "truthy",
    "int_env",
    "float_env",
    "str_env",
    "max_tool_output_env",
    "typed_results_enabled",
    "default_tool_timeout",
    "include_defaults_env",
    "resolve_include_defaults",
]
