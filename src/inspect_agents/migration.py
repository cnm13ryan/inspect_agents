from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from . import fs as _fs


def _resolve_builtin_tools(names: list[str] | None) -> list[object]:
    from inspect_agents import tools as builtin

    name_to_ctor = {
        "write_todos": builtin.write_todos,
        "write_file": builtin.write_file,
        "read_file": builtin.read_file,
        "ls": builtin.ls,
        "edit_file": builtin.edit_file,
    }

    selected = list(name_to_ctor.keys()) if names is None else names
    return [name_to_ctor[n]() for n in selected if n in name_to_ctor]


logger = logging.getLogger(__name__)


async def _apply_side_effect_calls(
    messages: list[Any], tools: Sequence[object], *, instance: str | None = None
) -> None:
    """Apply side-effecting tool calls when `submit` appears in same turn.

    Mirrors the inline logic previously embedded in `create_deep_agent`.
    - Finds the most recent assistant message with tool calls.
    - Filters out `submit`.
    - Replays via `execute_tools`.
    - Applies defensive Store fallbacks for `write_file` / `write_todos`.
    """
    try:
        # Find the most recent assistant message with tool calls
        idx = next(
            (i for i in range(len(messages) - 1, -1, -1) if getattr(messages[i], "tool_calls", None)),
            None,
        )
        if idx is not None:
            last = messages[idx]
            calls = [c for c in (last.tool_calls or []) if getattr(c, "function", "") != "submit"]
            if calls:
                # Build a synthetic conversation ending at the tool-call message
                # so execute_tools sees it as the last assistant message.
                msgs = list(messages[: idx + 1])
                # Create a shallow copy with filtered calls (pydantic model_copy)
                try:
                    last_filtered = last.model_copy(update={"tool_calls": calls})
                except Exception:
                    last.tool_calls = calls  # fallback in case model_copy unavailable
                    last_filtered = last
                msgs[-1] = last_filtered
                try:
                    from inspect_ai.model._call_tools import execute_tools

                    await execute_tools(msgs, list(tools))
                    try:
                        logger.debug(
                            "side_effects.execute_tools_invoked count=%d",
                            len(calls),
                        )
                    except Exception:
                        pass
                except Exception as exc:
                    try:
                        logger.debug(
                            "side_effects.execute_tools_failed count=%d error=%s",
                            len(calls),
                            str(exc) or exc.__class__.__name__,
                        )
                    except Exception:
                        pass

                    # Policy-aware fallback: skip when failure indicates an approval denial
                    try:
                        kind = getattr(exc, "type", None)
                        msg = str(getattr(exc, "message", "") or str(exc)).lower()
                        is_denial = (
                            (isinstance(kind, str) and kind.lower() in {"approval_denied", "approval-denied"})
                            or ("approvaldenied" in msg)
                            or ("approval denied" in msg)
                            or ("denied by approval" in msg)
                        )
                    except Exception:
                        is_denial = False

                    if is_denial:
                        try:
                            logger.debug("side_effects.approval_denied; skipping_fallback=true")
                        except Exception:
                            pass
                        return

                # Defensive fallback: if tools didn't execute (e.g., due to
                # stubbed environments), apply side-effects for common calls.
                try:
                    from inspect_ai.util._store_model import store_as

                    from inspect_agents.state import Files, Todo, Todos

                    wrote_files = 0
                    wrote_todos = 0
                    # Compute pending items by inspecting Store after execute_tools
                    pending: list[Any] = []
                    try:
                        files_state = store_as(Files, instance=instance) if instance else store_as(Files)
                        todos_state = store_as(Todos, instance=instance) if instance else store_as(Todos)
                    except Exception:
                        files_state = None  # type: ignore
                        todos_state = None  # type: ignore

                    for c in calls:
                        fn = getattr(c, "function", "")
                        args = getattr(c, "arguments", {}) or {}
                        try:
                            if fn == "write_file" and files_state is not None:
                                path = args.get("file_path")
                                content = args.get("content")
                                already = (
                                    isinstance(path, str)
                                    and isinstance(content, str)
                                    and files_state.get_file(path) == content
                                )
                                if not already:
                                    pending.append(c)
                                continue
                            if fn == "write_todos" and todos_state is not None:
                                raw_items = args.get("todos") or []
                                items: list[Todo] = []
                                for t in raw_items:
                                    try:
                                        items.append(Todo(**t))
                                    except Exception:
                                        pass
                                desired = [(t.content, t.status) for t in items]
                                current = [(t.content, t.status) for t in (todos_state.get_todos() or [])]
                                already = bool(items) and desired == current
                                if not already:
                                    pending.append(c)
                                continue
                        except Exception:
                            pending.append(c)
                    if files_state is None and todos_state is None:
                        pending = list(calls)

                    try:
                        logger.debug("side_effects.fallback_begin count=%d", len(pending))
                    except Exception:
                        pass
                    for c in pending:
                        fn = getattr(c, "function", "")
                        args = getattr(c, "arguments", {}) or {}
                        if fn == "write_file" and "file_path" in args and "content" in args:
                            try:
                                content = args["content"]
                                content_bytes = len(str(content).encode("utf-8"))
                                max_bytes = _fs.max_bytes()
                                if content_bytes > max_bytes:
                                    logger.debug(
                                        "side_effects.fallback_file_too_large path=%s actual_bytes=%d max_bytes=%d",
                                        args.get("file_path"),
                                        content_bytes,
                                        max_bytes,
                                    )
                                    # Skip oversize write to mirror tool limits behavior
                                else:
                                    files = store_as(Files, instance=instance) if instance else store_as(Files)
                                    files.put_file(args["file_path"], content)
                                    wrote_files += 1
                            except Exception:
                                # On any error, conservatively attempt write to avoid data loss
                                try:
                                    files = store_as(Files, instance=instance) if instance else store_as(Files)
                                    files.put_file(args["file_path"], args["content"])
                                    wrote_files += 1
                                except Exception:
                                    pass
                        elif fn == "write_todos" and "todos" in args:
                            todos = store_as(Todos, instance=instance) if instance else store_as(Todos)
                            items = []
                            for t in args["todos"]:
                                try:
                                    items.append(Todo(**t))
                                except Exception:
                                    pass
                            if items:
                                todos.set_todos(items)
                                wrote_todos += len(items)
                    try:
                        logger.debug(
                            "side_effects.fallback_done wrote_files=%d wrote_todos=%d",
                            wrote_files,
                            wrote_todos,
                        )
                    except Exception:
                        pass
                except Exception:
                    pass
    except Exception:
        # Best-effort; continue even if inspection/execution fails
        pass


def create_deep_agent(
    tools: Sequence[object] | None,
    instructions: str,
    *,
    model: Any | None = None,
    subagents: list[dict[str, Any]] | None = None,
    state_schema: Any | None = None,
    builtin_tools: list[str] | None = None,
    interrupt_config: dict[str, Any] | None = None,
    attempts: int = 1,
    truncation: str = "disabled",
) -> object:
    """Drop-in constructor with deepagents-style compatibility (backed by Inspect).

    Maps the familiar legacy deepagents surface to Inspect's ReAct agent,
    sub-agents, and optional approval policies. Unused params are accepted for
    parity.
    """
    from inspect_ai.agent._agent import agent as as_agent
    from inspect_ai.agent._react import react

    from inspect_agents.agents import BASE_PROMPT, build_subagents

    # Resolve built-ins and optional sub-agents
    base_tools = _resolve_builtin_tools(builtin_tools)
    extra_tools = list(tools or [])

    if subagents:
        extra_tools.extend(build_subagents(subagents, base_tools))

    # Build top-level ReAct supervisor
    full_prompt = (instructions or "").rstrip() + "\n\n" + BASE_PROMPT
    base_agent = react(
        prompt=full_prompt,
        tools=base_tools + extra_tools,
        model=model,
        attempts=attempts,
        submit=True,
        truncation=truncation,  # default: disabled
    )

    # Ensure side-effecting tool calls in the model's final message (e.g., write_file)
    # are applied even when combined with an immediate `submit`. React may terminate
    # without executing preceding calls when `submit` is present in the same turn.
    @as_agent
    def agent():
        async def execute(state):
            out = await base_agent(state)
            await _apply_side_effect_calls(out.messages, base_tools + extra_tools)
            return out

        return execute

    # If interrupts provided, convert to approval policies and wrap to init on call
    if interrupt_config:
        from inspect_ai.agent._agent import agent as as_agent  # re-import in stub-friendly scope

        from inspect_agents.approval import (
            activate_approval_policies,
            approval_from_interrupt_config,
        )

        policies = approval_from_interrupt_config(interrupt_config)

        @as_agent
        def with_approvals():
            async def execute(state):
                activate_approval_policies(policies)
                return await agent(state)

            return execute

        return with_approvals()

    return agent()


__all__ = ["create_deep_agent"]
