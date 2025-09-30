"""Files-tool observability instrumentation.

This module extracts profile/FS-root enrichment and tool-event logging from
tools_files.py into a dedicated component so logging concerns stop bleeding
into execution paths. This reduces cognitive load, clarifies boundaries, and
keeps observability evolution from forcing edits across ultra-large modules.

Refactored to use TelemetryService for core logging functionality.
"""

from __future__ import annotations

import os
from typing import Any

from .settings import fs_root as _fs_root
from .settings import truthy as _truthy
from .telemetry import get_service as _get_telemetry_service


def _parse_profile(profile_str: str) -> tuple[str, str, str]:
    """Parse INSPECT_PROFILE format T1.H2.N0 -> (t, h, n)."""
    parts = profile_str.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid profile format: {profile_str}")

    t, h, n = parts
    if not (t.startswith("T") and h.startswith("H") and n.startswith("N")):
        raise ValueError(f"Invalid profile format: {profile_str}")

    return t, h, n


class FilesInstrumentation:
    """Encapsulates observability concerns for files:* tools.

    This class provides profile context enrichment and tool event logging
    specifically for files operations while composing with TelemetryService
    for core functionality.
    """

    def __init__(self) -> None:
        """Initialize instrumentation with TelemetryService integration."""
        self._telemetry = _get_telemetry_service()
        # Create augmented logger that enriches extra with profile context
        self._augmented_logger = self._telemetry.create_augmented_logger(self._augment_extra_for_files)

    def profile_extra(self) -> dict[str, Any]:
        """Return optional profile/fs_root fields for observability logs.

        Controlled by env flags:
        - INSPECT_OBS_INCLUDE_PROFILE: when truthy, include t/h/n (if available)
          and fs_root in the tool_event payload.
        - INSPECT_OBS_REDACT_PATHS: when truthy, redact path-like values
          (fs_root) to avoid leaking host paths in logs.
        """
        try:
            if not _truthy(os.getenv("INSPECT_OBS_INCLUDE_PROFILE")):
                return {}

            # fs_root is always included when the flag is enabled
            root = _fs_root()
            if _truthy(os.getenv("INSPECT_OBS_REDACT_PATHS")):
                try:
                    # Redact by keeping only the basename; if that fails, mask
                    import os as _os

                    redacted_root = _os.path.basename(root.rstrip(_os.sep)) or "[redacted]"
                except Exception:
                    redacted_root = "[redacted]"
                fs_root_val: Any = redacted_root
            else:
                fs_root_val = root

            # Parse INSPECT_PROFILE if present; ignore on parse errors
            t: str | None = None
            h: str | None = None
            n: str | None = None
            raw = (os.getenv("INSPECT_PROFILE") or "").strip()
            if raw:
                try:
                    t, h, n = _parse_profile(raw)
                except Exception:
                    # Do not raise; simply omit t/h/n when invalid
                    t = h = n = None

            out: dict[str, Any] = {"fs_root": fs_root_val}
            if t and h and n:
                out.update({"t": t, "h": h, "n": n})
            return out
        except Exception:
            # Never let observability impact control flow
            return {}

    def merge_extra(self, extra: dict[str, Any] | None) -> dict[str, Any] | None:
        """Merge profile extra with provided extra without overwriting its keys.

        When disabled via env, returns the original extra unchanged.
        """
        try:
            base = self.profile_extra()
            if not base:
                return extra
            if extra is None:
                return base
            # Preserve existing keys by letting `extra` win on conflicts
            merged = dict(base)
            merged.update(extra)
            return merged
        except Exception:
            return extra

    def _augment_extra_for_files(self, extra: dict[str, Any] | None) -> dict[str, Any] | None:
        """Internal augmentation function for files:* events.

        This is passed to TelemetryService.create_augmented_logger to enable
        profile enrichment without duplicating logging logic.
        """
        return self.merge_extra(extra)

    def log_tool_event(
        self,
        *,
        name: str,
        phase: str,
        args: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
        t0: float | None = None,
    ) -> float:
        """Thin wrapper that augments files:* events with profile context.

        Delegates to TelemetryService via augmented logger for files:* events,
        or directly to base service for other events.
        """
        # Only augment files:* events
        if isinstance(name, str) and name.startswith("files:"):
            return self._augmented_logger(name=name, phase=phase, args=args, extra=extra, t0=t0)
        else:
            return self._telemetry.log_tool_event(name=name, phase=phase, args=args, extra=extra, t0=t0)

    def store_context_kwargs(self) -> dict[str, Any]:
        """Return kwargs for creating StoreOpsContext with this instrumentation.

        This provides the log_tool_event function that should be injected into
        StoreOpsContext to ensure consistent observability behavior across
        both sandbox and store modes.
        """
        return {"log_tool_event": self.log_tool_event}


# Default instance for backward compatibility
_default_instrumentation = FilesInstrumentation()


# Public API functions that mirror the original tools_files.py interface
def profile_extra() -> dict[str, Any]:
    """Return optional profile/fs_root fields for observability logs."""
    return _default_instrumentation.profile_extra()


def merge_extra(extra: dict[str, Any] | None) -> dict[str, Any] | None:
    """Merge profile extra with provided extra without overwriting its keys."""
    return _default_instrumentation.merge_extra(extra)


def log_tool_event(
    *,
    name: str,
    phase: str,
    args: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
    t0: float | None = None,
) -> float:
    """Thin wrapper that augments files:* events with profile context."""
    return _default_instrumentation.log_tool_event(name=name, phase=phase, args=args, extra=extra, t0=t0)


def store_context_kwargs() -> dict[str, Any]:
    """Return kwargs for creating StoreOpsContext with instrumentation."""
    return _default_instrumentation.store_context_kwargs()
