from __future__ import annotations

from .facade import (
    activate_approval_policies,
    approval_chain,
    approval_from_interrupt_config,
    approval_preset,
    handoff_exclusive_policy,
    parallel_kill_switch_policy,
    redact_arguments,
)

"""Approval facade package.

This package preserves the historical ``inspect_agents.approval`` surface while
organising the implementation across smaller modules.
"""

__all__ = [
    "activate_approval_policies",
    "approval_chain",
    "approval_from_interrupt_config",
    "approval_preset",
    "handoff_exclusive_policy",
    "parallel_kill_switch_policy",
    "redact_arguments",
]
