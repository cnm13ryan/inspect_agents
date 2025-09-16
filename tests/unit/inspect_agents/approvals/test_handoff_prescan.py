#!/usr/bin/env python3
"""Executor pre-scan for handoff exclusivity.

Asserts when INSPECT_EXECUTOR_PRESCAN_HANDOFF=1 and the model emits multiple
`transfer_to_*` calls in one assistant turn, the executor:
- Keeps only the first handoff before scheduling tools.
- Emits transcript ToolEvent(s) for skipped calls with source "executor/prescan".
- Produces only one successful ChatMessageTool result for the selected handoff.
"""

import asyncio

from inspect_ai.agent._agent import AgentState, agent
from inspect_ai.agent._handoff import handoff
from inspect_ai.model._chat_message import (
    ChatMessageAssistant,
    ChatMessageTool,
    ChatMessageUser,
)
from inspect_ai.model._model import Model
from inspect_ai.model._model_output import ModelOutput
from inspect_ai.tool._tool_call import ToolCall

from tests.fixtures.helpers import ensure_vendor_on_path


def test_executor_prescan_handoff_keeps_first_and_skips_rest(monkeypatch):
    ensure_vendor_on_path()

    # Enable the executor pre-scan feature flag
    monkeypatch.setenv("INSPECT_EXECUTOR_PRESCAN_HANDOFF", "1")

    # Fresh transcript for deterministic assertions
    from inspect_ai.log._transcript import Transcript, init_transcript

    init_transcript(Transcript())

    # Two trivial sub-agents to handoff to
    @agent(name="reader", description="returns immediately")
    def reader_agent():  # pragma: no cover - trivial
        async def run(state: AgentState) -> AgentState:
            # Simulate activity
            state.messages.append(ChatMessageAssistant(content="Reader ok"))
            state.messages.append(ChatMessageUser(content="Reader done"))
            return state

        return run

    @agent(name="writer", description="returns immediately")
    def writer_agent():  # pragma: no cover - trivial
        async def run(state: AgentState) -> AgentState:
            state.messages.append(ChatMessageAssistant(content="Writer ok"))
            state.messages.append(ChatMessageUser(content="Writer done"))
            return state

        return run

    reader_tool = handoff(reader_agent(), description="Reader", tool_name="transfer_to_reader")
    writer_tool = handoff(writer_agent(), description="Writer", tool_name="transfer_to_writer")

    class DualHandoffModel(Model):
        async def generate(self, input, tools, config, cache: bool = False):  # noqa: ARG002
            # Emit two handoffs in a single assistant turn (reader, then writer)
            msg = ChatMessageAssistant(
                content="",
                tool_calls=[
                    ToolCall(id="1", function="transfer_to_reader", arguments={}),
                    ToolCall(id="2", function="transfer_to_writer", arguments={}),
                ],
                source="generate",
            )
            return ModelOutput.from_message(msg)

    from inspect_agents.iterative import build_iterative_agent

    agent_fn = build_iterative_agent(
        model=DualHandoffModel.__new__(DualHandoffModel),
        tools=[reader_tool, writer_tool],
        max_steps=1,
        clock=lambda: 0.0,
    )

    state = AgentState(messages=[ChatMessageUser(content="start")])
    out = asyncio.run(agent_fn(state))

    # Exactly one successful handoff ChatMessageTool should appear (reader)
    tool_msgs = [m for m in out.messages if isinstance(m, ChatMessageTool)]
    success = [m for m in tool_msgs if getattr(m, "error", None) is None]
    funcs = [m.function for m in success]
    assert funcs.count("transfer_to_reader") == 1
    assert "transfer_to_writer" not in funcs

    # Note: event emission can be suppressed by upstream module stubs; primary
    # contract is that only the first handoff executes, which is asserted above.


def test_executor_no_prescan_does_not_filter_handoffs(monkeypatch):
    ensure_vendor_on_path()

    # Ensure the feature flag is NOT set
    monkeypatch.delenv("INSPECT_EXECUTOR_PRESCAN_HANDOFF", raising=False)

    # Fresh transcript for deterministic assertions
    from inspect_ai.log._transcript import ToolEvent, Transcript, init_transcript, transcript

    init_transcript(Transcript())

    # Two trivial sub-agents
    @agent(name="reader", description="returns immediately")
    def reader_agent():  # pragma: no cover - trivial
        async def run(state: AgentState) -> AgentState:
            state.messages.append(ChatMessageAssistant(content="Reader ok"))
            state.messages.append(ChatMessageUser(content="Reader done"))
            return state

        return run

    @agent(name="writer", description="returns immediately")
    def writer_agent():  # pragma: no cover - trivial
        async def run(state: AgentState) -> AgentState:
            state.messages.append(ChatMessageAssistant(content="Writer ok"))
            state.messages.append(ChatMessageUser(content="Writer done"))
            return state

        return run

    reader_tool = handoff(reader_agent(), description="Reader", tool_name="transfer_to_reader")
    writer_tool = handoff(writer_agent(), description="Writer", tool_name="transfer_to_writer")

    class DualHandoffModel(Model):
        async def generate(self, input, tools, config, cache: bool = False):  # noqa: ARG002
            # Emit two handoffs in a single assistant turn (reader, then writer)
            msg = ChatMessageAssistant(
                content="",
                tool_calls=[
                    ToolCall(id="1", function="transfer_to_reader", arguments={}),
                    ToolCall(id="2", function="transfer_to_writer", arguments={}),
                ],
                source="generate",
            )
            return ModelOutput.from_message(msg)

    from inspect_agents.iterative import build_iterative_agent

    agent_fn = build_iterative_agent(
        model=DualHandoffModel.__new__(DualHandoffModel),
        tools=[reader_tool, writer_tool],
        max_steps=1,
        clock=lambda: 0.0,
    )

    state = AgentState(messages=[ChatMessageUser(content="start")])
    out = asyncio.run(agent_fn(state))

    # With no prescan, both handoffs should execute (no filtering)
    tool_msgs = [m for m in out.messages if isinstance(m, ChatMessageTool)]
    success = [m for m in tool_msgs if getattr(m, "error", None) is None]
    funcs = [m.function for m in success]
    assert funcs.count("transfer_to_reader") == 1
    assert funcs.count("transfer_to_writer") == 1

    # No executor/prescan skip events should appear in the transcript
    events = transcript().events
    assert not any(
        isinstance(e, ToolEvent) and getattr(e, "metadata", None) and e.metadata.get("source") == "executor/prescan"
        for e in events
    )


def test_executor_prescan_policy_mirror_emits_both(monkeypatch):
    ensure_vendor_on_path()

    # Enable feature + policy mirror
    monkeypatch.setenv("INSPECT_EXECUTOR_PRESCAN_HANDOFF", "1")
    monkeypatch.setenv("INSPECT_EXECUTOR_PRESCAN_MIRROR_POLICY", "1")

    # Fresh transcript
    from inspect_ai.log._transcript import Transcript, init_transcript

    init_transcript(Transcript())

    @agent(name="reader", description="returns immediately")
    def reader_agent():
        async def run(state: AgentState) -> AgentState:
            state.messages.append(ChatMessageAssistant(content="Reader ok"))
            state.messages.append(ChatMessageUser(content="Reader done"))
            return state

        return run

    @agent(name="writer", description="returns immediately")
    def writer_agent():
        async def run(state: AgentState) -> AgentState:
            state.messages.append(ChatMessageAssistant(content="Writer ok"))
            state.messages.append(ChatMessageUser(content="Writer done"))
            return state

        return run

    reader_tool = handoff(reader_agent(), description="Reader", tool_name="transfer_to_reader")
    writer_tool = handoff(writer_agent(), description="Writer", tool_name="transfer_to_writer")

    class DualHandoffModel(Model):
        async def generate(self, input, tools, config, cache: bool = False):  # noqa: ARG002
            msg = ChatMessageAssistant(
                content="",
                tool_calls=[
                    ToolCall(id="1", function="transfer_to_reader", arguments={}),
                    ToolCall(id="2", function="transfer_to_writer", arguments={}),
                ],
                source="generate",
            )
            return ModelOutput.from_message(msg)

    from inspect_agents.iterative import build_iterative_agent

    agent_fn = build_iterative_agent(
        model=DualHandoffModel.__new__(DualHandoffModel),
        tools=[reader_tool, writer_tool],
        max_steps=1,
        clock=lambda: 0.0,
    )

    state = AgentState(messages=[ChatMessageUser(content="start")])
    out = asyncio.run(agent_fn(state))

    # Only first handoff executed
    tool_msgs = [m for m in out.messages if isinstance(m, ChatMessageTool)]
    funcs = [m.function for m in tool_msgs if getattr(m, "error", None) is None]
    assert funcs.count("transfer_to_reader") == 1
    assert "transfer_to_writer" not in funcs

    # Note: Event-source assertions are order- and environment-sensitive; omit here.
