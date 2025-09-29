from __future__ import annotations

"""Public facade for Inspect Agents approval helpers.

The functions re-exported here depend on Inspect's private approval modules
(e.g. ``inspect_ai.approval._policy``) that callers frequently stub in tests.
Imports are therefore kept local within helper modules, and this facade simply
coordinates their availability.
"""

from typing import Any

from .interrupts import approval_from_interrupt_config
from .presets import approval_preset
from .redaction import redact_arguments
from .registry import (
    approval_chain,
    handoff_exclusive_policy,
    parallel_kill_switch_policy,
)

__all__ = [
    "approval_from_interrupt_config",
    "activate_approval_policies",
    "approval_preset",
    "redact_arguments",
    "handoff_exclusive_policy",
    "parallel_kill_switch_policy",
    "approval_chain",
]


def activate_approval_policies(policies: list[Any] | None) -> None:
    """Activate approval policies via Inspect's ``init_tool_approval`` entrypoint."""
    if not policies:
        return
    try:
        from inspect_ai.approval._apply import init_tool_approval  # type: ignore

        init_tool_approval(policies)
    except Exception:
        # Tests may stub out ``init_tool_approval``; treat absence as a no-op.
        pass
