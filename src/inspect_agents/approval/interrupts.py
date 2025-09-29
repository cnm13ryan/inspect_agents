from __future__ import annotations

"""Compatibility helpers for DeepAgents-style interrupt configuration.

This module depends on Inspect's private approval internals
(`inspect_ai.approval._approval`, `_policy`, `_apply`) and tags approvers using
`inspect_ai._util.registry`. Tests commonly stub these modules, so imports remain
inside function bodies to avoid hard failures when Inspect is absent.
"""

from typing import Any


def approval_from_interrupt_config(cfg: dict[str, Any]) -> list[Any]:
    """Convert legacy interrupt config dictionaries into Inspect policies."""
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

    policies: list[ApprovalPolicy] = []

    for tool, conf in (cfg or {}).items():
        conf_dict = conf if isinstance(conf, dict) else {}

        allow_accept = bool(conf_dict.get("allow_accept", True))
        allow_edit = bool(conf_dict.get("allow_edit", True))
        allow_ignore = bool(conf_dict.get("allow_ignore", False))
        if allow_ignore:
            raise ValueError("allow_ignore=True not supported by Inspect approvals")

        decision: str = conf_dict.get("decision", "approve")
        explanation: str | None = conf_dict.get("explanation")
        mod_args = conf_dict.get("modified_args", conf_dict.get("modify_args"))
        mod_fn = conf_dict.get("modified_function", conf_dict.get("modify_function"))

        async def _approve(message, call: ToolCall, view, history):  # type: ignore[no-redef]
            dec = decision
            if dec == "approve":
                if not allow_accept:
                    return Approval(decision="reject", explanation=explanation or "accept not allowed")
                return Approval(decision="approve", explanation=explanation)
            if dec == "modify":
                if not allow_edit:
                    return Approval(decision="reject", explanation=explanation or "edit not allowed")
                new_call = call
                if mod_args is not None or mod_fn is not None:
                    new_call = ToolCall(
                        id=call.id,
                        function=(mod_fn or call.function),
                        arguments=(mod_args or call.arguments),
                        parse_error=call.parse_error,
                        view=call.view,
                        type=call.type,
                    )
                return Approval(decision="modify", modified=new_call, explanation=explanation)
            if dec == "reject":
                return Approval(decision="reject", explanation=explanation)
            if dec == "terminate":
                return Approval(decision="terminate", explanation=explanation)
            return Approval(decision="approve", explanation=explanation)

        info = RegistryInfo(type="approver", name=f"inline/{tool}")
        registry_tag(lambda: None, _approve, info)
        for attr in ("__registry_info__", "REGISTRY_INFO"):
            try:
                setattr(_approve, attr, info)
            except Exception:
                pass

        policies.append(ApprovalPolicy(approver=_approve, tools=tool))

    return policies


__all__ = ["approval_from_interrupt_config"]
