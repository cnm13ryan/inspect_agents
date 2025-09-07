import asyncio
import types

import pytest

from inspect_agents._conversation import prune_messages
from inspect_agents.iterative import build_iterative_agent


def _ns(role: str, content=None, **kw):
    return types.SimpleNamespace(role=role, content=content, **kw)


@pytest.mark.truncation
def test_prune_messages_drops_orphan_tool_and_salvages_pair():
    # System + first user always preserved
    sys_msg = _ns("system", "S")
    u1 = _ns("user", "U1")

    # Older assistant→tool pair we expect to be salvaged if no tools remain in tail
    a_old = _ns(
        "assistant",
        "",  # content not relevant
        tool_calls=[types.SimpleNamespace(id="1", function="ls", arguments={})],
    )
    t_old = _ns("tool", "ok", tool_call_id="1")

    # Add some filler user turns and a late orphan tool (no parent assistant in tail)
    u2 = _ns("user", "U2")
    u3 = _ns("user", "U3")
    orphan_tool = _ns("tool", "junk", tool_call_id="999")
    u4 = _ns("user", "U4")

    msgs = [sys_msg, u1, a_old, t_old, u2, u3, orphan_tool, u4]

    # Keep a small tail to exclude the old pair from the natural tail window
    pruned = prune_messages(msgs, keep_last=2)

    # Structure: system, first user, then salvaged assistant+tool, then tail user msgs
    roles = [m.role for m in pruned]
    assert roles[:2] == ["system", "user"]
    # The salvaged pair must appear (assistant followed by tool)
    assert any(getattr(m, "tool_calls", None) for m in pruned), "assistant with tool_calls not found"
    assert any(getattr(m, "tool_call_id", None) == "1" for m in pruned), "paired tool not found"
    # Orphan tool must be dropped
    assert not any(getattr(m, "tool_call_id", None) == "999" for m in pruned)


@pytest.mark.truncation
def test_overflow_model_length_appends_hint_then_prunes(monkeypatch):
    from inspect_ai.agent._agent import AgentState
    from inspect_ai.model._chat_message import ChatMessageAssistant, ChatMessageSystem, ChatMessageUser
    from inspect_ai.model._model import Model
    from inspect_ai.model._model_output import ModelOutput

    # Stub retry wrapper to simulate provider returning model_length with a small reply
    async def fake_generate_with_retry_time(model, *, input, tools, cache, config, **_):  # noqa: ARG001
        out = ModelOutput.from_message(
            ChatMessageAssistant(content="small", source="generate"),
            stop_reason="model_length",
        )
        return out, 0.0

    monkeypatch.setattr(
        "inspect_agents._model_retry.generate_with_retry_time",
        fake_generate_with_retry_time,
        raising=True,
    )

    # Build agent with one step; disable _prune_history via max_turns=0 so overflow path is exercised
    class DummyModel(Model):
        async def generate(self, input, tools, config, cache: bool = False):  # noqa: ARG002
            # Not called thanks to stub; keep for interface completeness
            return ModelOutput.from_message(ChatMessageAssistant(content="noop"))

    agent = build_iterative_agent(
        model=DummyModel.__new__(DummyModel),
        max_steps=1,
        max_turns=0,
        prune_keep_last=2,
        per_msg_token_cap=None,  # keep truncation out of the picture for determinism
    )

    # Seed conversation long enough that pruning would have a visible effect
    msgs = [
        ChatMessageSystem(content="sys"),
        ChatMessageUser(content="U0"),
        ChatMessageUser(content="U1"),
        ChatMessageAssistant(content="A1"),
        ChatMessageUser(content="U2"),
        ChatMessageAssistant(content="A2"),
    ]
    state = AgentState(messages=msgs)

    # Run once; on first iteration model_length triggers: append hint, then prune, then continue -> step limit exits
    new_state = asyncio.run(agent(state))

    contents = [getattr(m, "text", getattr(m, "content", "")) for m in new_state.messages]
    # Overflow hint is appended but removed by prune_messages; it should not remain
    assert "Context too long; please summarize recent steps and continue." not in contents
    # Pruning after overflow keeps: system + first user + last keep_last messages
    # So length should be <= 2 (prefix) + 2 (keep_last)
    assert len(new_state.messages) <= 4
    # The assistant output from the overflow step should still be present
    assert any((str(c) or "").strip() == "small" for c in contents)


# (adjacency behavior tested in a separate commit)


@pytest.mark.truncation
def test_prune_history_drops_non_adjacent_tool(monkeypatch):
    """_prune_history keeps first system+user and drops tool not adjacent to assistant."""
    from inspect_ai.agent._agent import AgentState
    from inspect_ai.model._chat_message import (
        ChatMessageAssistant,
        ChatMessageSystem,
        ChatMessageTool,
        ChatMessageUser,
    )
    from inspect_ai.model._model import Model
    from inspect_ai.model._model_output import ModelOutput

    # Use a dummy model that returns a tiny assistant once so the loop runs
    class DummyModel(Model):
        async def generate(self, input, tools, config, cache: bool = False):  # noqa: ARG002
            return ModelOutput.from_message(ChatMessageAssistant(content="ok", source="generate"))

    agent = build_iterative_agent(
        model=DummyModel.__new__(DummyModel),
        max_steps=1,
        max_turns=2,  # enable _prune_history windowing
        prune_after_messages=None,  # disable threshold prune to isolate _prune_history
        per_msg_token_cap=None,
    )

    # Tail has: user, assistant, user, tool (tool is not adjacent to assistant)
    msgs = [
        ChatMessageSystem(content="sys"),
        ChatMessageUser(content="u0"),
        ChatMessageUser(content="u1"),
        ChatMessageAssistant(content="a1"),
        ChatMessageUser(content="u2"),  # breaks adjacency
        ChatMessageTool(content="t1", tool_call_id="xyz"),
    ]
    state = AgentState(messages=msgs)

    new_state = asyncio.run(agent(state))

    # Expect first system+user preserved; tool not adjacent to assistant is dropped
    roles = [m.__class__.__name__ for m in new_state.messages]
    assert roles[0] == "ChatMessageSystem"
    assert any(r == "ChatMessageUser" for r in roles[:2])
    assert all(not isinstance(m, ChatMessageTool) for m in new_state.messages)
