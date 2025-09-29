from __future__ import annotations

"""Approval policy helpers that wrap Inspect-specific internals.

Each policy imports Inspect's private modules lazily so unit tests can stub the
APIs without requiring the real Inspect runtime. When logging, we reuse the
project-local observability hook (`inspect_agents.observability.log_tool_event`).
"""

import os
from typing import Any

from inspect_agents.settings import truthy as _truthy

__all__ = [
    "handoff_exclusive_policy",
    "parallel_kill_switch_policy",
    "approval_chain",
]


def _get(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        try:
            return obj.get(name, default)  # type: ignore[attr-defined]
        except Exception:
            return default


def _last_assistant_with_calls(message: Any, history: list[Any]) -> Any | None:
    tool_calls = _get(message, "tool_calls") if message is not None else None
    if isinstance(tool_calls, (list, tuple)) and tool_calls:
        return message
    for msg in reversed(list(history or [])):
        tool_calls = _get(msg, "tool_calls")
        if isinstance(tool_calls, (list, tuple)) and tool_calls:
            return msg
    return None


def _first_handoff_from_message(msg: Any) -> Any | None:
    for tc in _get(msg, "tool_calls") or []:
        fn = _get(tc, "function", "")
        if isinstance(fn, str) and fn.startswith("transfer_to_"):
            return tc
    return None


def _first_non_handoff_id(msg: Any) -> Any:
    for tc in _get(msg, "tool_calls") or []:
        fn = _get(tc, "function", "")
        if not (isinstance(fn, str) and fn.startswith("transfer_to_")):
            return _get(tc, "id")
    return None


def handoff_exclusive_policy() -> list[Any]:
    """Return a policy that enforces first-handoff exclusivity per assistant turn."""
    from inspect_ai.approval._approval import Approval  # type: ignore

    try:
        from inspect_ai.approval._policy import ApprovalPolicy  # type: ignore
    except Exception:

        class ApprovalPolicy:  # type: ignore
            def __init__(self, approver, tools):
                self.approver = approver
                self.tools = tools

    from inspect_ai._util.registry import RegistryInfo, registry_tag  # type: ignore
    from inspect_ai.tool._tool_call import ToolCall  # type: ignore

    async def approver(message, call: ToolCall, view, history):  # type: ignore[no-redef]
        source = _last_assistant_with_calls(message, history)
        if source is None:
            return Approval(decision="escalate")

        selected = _first_handoff_from_message(source)
        if selected is None:
            return Approval(decision="approve")

        selected_id = _get(selected, "id")
        current_is_handoff = isinstance(call.function, str) and call.function.startswith("transfer_to_")
        if current_is_handoff and call.id == selected_id:
            return Approval(decision="approve")

        try:
            from ..observability import log_tool_event as _log_tool_event

            _log_tool_event(
                name="handoff_exclusive",
                phase="skipped",
                extra={
                    "selected_handoff_id": selected_id,
                    "skipped_function": call.function,
                },
            )
        except Exception:
            pass

        try:
            from inspect_ai.log._transcript import ToolEvent, transcript  # type: ignore
            from inspect_ai.tool._tool_call import ToolCallError  # type: ignore

            ev = ToolEvent(
                id=str(call.id),
                function=str(call.function),
                arguments=dict(call.arguments or {}),
                pending=False,
                error=ToolCallError("approval", "Skipped due to handoff"),
                metadata={
                    "selected_handoff_id": selected_id,
                    "skipped_function": call.function,
                    "source": "policy/handoff_exclusive",
                },
            )
            transcript()._event(ev)
        except Exception:
            pass

        return Approval(decision="reject", explanation="Skipped due to handoff exclusivity")

    registry_tag(lambda: None, approver, RegistryInfo(type="approver", name="policy/handoff_exclusive"))
    return [ApprovalPolicy(approver=approver, tools="*")]


def parallel_kill_switch_policy() -> list[Any]:
    """Return a policy that disables parallel tool execution when kill-switch envs are set."""
    from inspect_ai.approval._approval import Approval  # type: ignore

    try:
        from inspect_ai.approval._policy import ApprovalPolicy  # type: ignore
    except Exception:

        class ApprovalPolicy:  # type: ignore
            def __init__(self, approver, tools):
                self.approver = approver
                self.tools = tools

    from inspect_ai._util.registry import RegistryInfo, registry_tag  # type: ignore
    from inspect_ai.tool._tool_call import ToolCall  # type: ignore

    async def approver(message, call: ToolCall, view, history):  # type: ignore[no-redef]
        if not (
            _truthy(os.getenv("INSPECT_TOOL_PARALLELISM_DISABLE"))
            or _truthy(os.getenv("INSPECT_DISABLE_TOOL_PARALLEL"))
        ):
            return Approval(decision="escalate")

        source = _last_assistant_with_calls(message, history)
        if source is None:
            return Approval(decision="escalate")

        tool_calls = _get(source, "tool_calls") or []
        if not isinstance(tool_calls, (list, tuple)) or len(tool_calls) <= 1:
            return Approval(decision="escalate")

        if _first_handoff_from_message(source) is not None:
            return Approval(decision="escalate")

        first_allowed = _first_non_handoff_id(source)
        if first_allowed is None:
            return Approval(decision="escalate")

        if call.id == first_allowed:
            return Approval(decision="approve")

        try:
            from ..observability import log_tool_event as _log_tool_event

            _log_tool_event(
                name="parallel_kill_switch",
                phase="skipped",
                extra={
                    "first_allowed_id": first_allowed,
                    "skipped_function": call.function,
                },
            )
        except Exception:
            pass

        try:
            from inspect_ai.log._transcript import ToolEvent, transcript  # type: ignore
            from inspect_ai.tool._tool_call import ToolCallError  # type: ignore

            ev = ToolEvent(
                id=str(call.id),
                function=str(call.function),
                arguments=dict(call.arguments or {}),
                pending=False,
                error=ToolCallError("approval", "Parallel disabled: only first tool approved"),
                metadata={
                    "first_allowed_id": first_allowed,
                    "skipped_function": call.function,
                    "source": "policy/parallel_kill_switch",
                },
            )
            transcript()._event(ev)
        except Exception:
            pass

        return Approval(decision="reject", explanation="Parallel disabled: only first tool approved")

    registry_tag(lambda: None, approver, RegistryInfo(type="approver", name="policy/parallel_kill_switch"))
    return [ApprovalPolicy(approver=approver, tools="*")]


def approval_chain(
    *policies: Any,
    include_exclusivity: bool = True,
    include_kill_switch: bool = True,
) -> list[Any]:
    """Compose approval policies with standard exclusivity and kill-switch ordering."""
    chain: list[Any] = []

    if include_exclusivity:
        try:
            chain.extend(handoff_exclusive_policy())
        except Exception:
            pass

    if include_kill_switch:
        try:
            chain.extend(parallel_kill_switch_policy())
        except Exception:
            pass

    for p in policies:
        if not p:
            continue
        if isinstance(p, list):
            chain.extend(p)
        else:
            chain.append(p)

    return chain
