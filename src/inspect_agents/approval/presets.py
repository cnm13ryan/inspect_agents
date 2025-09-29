from __future__ import annotations

"""Preset approval chains used by Inspect Agents runners.

This module builds policy lists using Inspect's private approval APIs and relies
on the registry helpers defined in :mod:`inspect_agents.approval.registry`.
"""

import json
import re
from typing import Any

from .redaction import redact_arguments
from .registry import approval_chain

__all__ = ["approval_preset"]


def approval_preset(preset: str) -> list[Any]:
    """Return preset approval policies for ``ci``, ``dev`` and ``prod``."""
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

    sensitive = re.compile(r"^(write_file|text_editor|bash|python|web_browser_)")

    def _as_dict(obj: Any) -> dict[str, Any]:
        try:
            if isinstance(obj, dict):
                return obj
            if isinstance(obj, str):
                return json.loads(obj)
        except Exception:
            pass
        return {}

    _fs_mutation_cmds = {"write", "edit", "trash", "mkdir", "move"}

    def _is_sensitive_fs_mutation(call: Any) -> bool:
        try:
            if getattr(call, "function", "") != "files":
                return False
            args = _as_dict(getattr(call, "arguments", {}))
            params = args.get("params") if isinstance(args.get("params"), (dict, str)) else args
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except Exception:
                    params = {}
            if isinstance(params, dict):
                cmd = params.get("command")
                if cmd is None and isinstance(params.get("root"), dict):
                    cmd = params.get("root", {}).get("command")  # type: ignore[assignment]
                return cmd in _fs_mutation_cmds
        except Exception:
            return False
        return False

    async def approve_all(message, call: ToolCall, view, history):  # type: ignore
        return Approval(decision="approve")

    registry_tag(lambda: None, approve_all, RegistryInfo(type="approver", name="preset/approve_all"))

    async def dev_gate(message, call: ToolCall, view, history):  # type: ignore
        if sensitive.match(call.function) or _is_sensitive_fs_mutation(call):
            expl = (
                json.dumps(redact_arguments(_as_dict(call.arguments)))
                if getattr(call, "function", "") == "files"
                else "dev: escalate sensitive tool"
            )
            return Approval(decision="escalate", explanation=expl)
        return Approval(decision="approve")

    registry_tag(lambda: None, dev_gate, RegistryInfo(type="approver", name="preset/dev_gate"))

    async def reject_all(message, call: ToolCall, view, history):  # type: ignore
        return Approval(decision="reject", explanation="Rejected by policy")

    registry_tag(lambda: None, reject_all, RegistryInfo(type="approver", name="preset/reject_all"))

    async def prod_gate(message, call: ToolCall, view, history):  # type: ignore
        if sensitive.match(call.function) or _is_sensitive_fs_mutation(call):
            red = redact_arguments(_as_dict(call.arguments))
            return Approval(decision="terminate", explanation=json.dumps(red))
        return Approval(decision="approve")

    registry_tag(lambda: None, prod_gate, RegistryInfo(type="approver", name="preset/prod_gate"))

    match preset:
        case "ci":
            return [ApprovalPolicy(approver=approve_all, tools="*")]
        case "dev":
            return approval_chain(
                [
                    ApprovalPolicy(approver=dev_gate, tools="*"),
                    ApprovalPolicy(approver=reject_all, tools="*"),
                ]
            )
        case "prod":
            return approval_chain([ApprovalPolicy(approver=prod_gate, tools="*")])
        case _:
            raise ValueError(f"Unknown approval preset: {preset}")
