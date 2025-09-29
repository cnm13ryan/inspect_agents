from __future__ import annotations

"""Redaction utilities for approval payloads.

This module is self-contained and does not depend on Inspect internals so it can
be imported safely from tests that stub Inspect modules.
"""

from typing import Any

REDACT_KEYS = {"api_key", "authorization", "token", "password", "file_text", "content"}


def _redact_value(key: str, value: Any) -> Any:
    """Recursively redact values whose key is known to contain sensitive data."""
    if key in REDACT_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {k: _redact_value(k, v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        out: list[Any] = []
        for item in value:
            if isinstance(item, dict):
                out.append({k: _redact_value(k, v) for k, v in item.items()})
            else:
                out.append(item)
        return out
    return value


def redact_arguments(args: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive fields from tool argument dictionaries."""
    return {k: _redact_value(k, v) for k, v in (args or {}).items()}


__all__ = ["redact_arguments", "REDACT_KEYS"]
