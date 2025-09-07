import json
import logging

import pytest


def _collect_limits_events(records):
    events = []
    for rec in records:
        msg = rec.getMessage()
        if isinstance(msg, str) and msg.startswith("tool_event "):
            try:
                payload = json.loads(msg[len("tool_event ") :])
            except Exception:
                continue
            if payload.get("tool") == "limits" and payload.get("phase") == "error":
                events.append(payload)
    return events


@pytest.mark.asyncio
async def test_limits_event_on_return_tuple(caplog, monkeypatch):
    # Keep things offline/deterministic
    # Offline by default via root env guard

    # Capture our package logs
    caplog.set_level(logging.INFO, logger="inspect_agents")
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    # Build a simple supervisor that issues a submit tool call
    from inspect_ai.agent._agent import AgentState, agent
    from inspect_ai.model._chat_message import ChatMessageAssistant
    from inspect_ai.tool._tool_call import ToolCall

    from inspect_agents.agents import build_supervisor

    @agent
    def toy_submit_model():
        async def execute(state: AgentState, tools):
            state.messages.append(
                ChatMessageAssistant(
                    content="",
                    tool_calls=[ToolCall(id="1", function="submit", arguments={"answer": "DONE"})],
                )
            )
            return state

        return execute

    agent_obj = build_supervisor(prompt="You are helpful.", tools=[], attempts=1, model=toy_submit_model())

    from inspect_ai.util import LimitExceededError, time_limit

    from inspect_agents.run import run_agent

    before = len(caplog.records)
    # Supply a zero time limit so Inspect returns (state, err)
    result = await run_agent(
        agent_obj,
        "start",
        limits=[time_limit(0)],
        return_limit_error=True,
    )

    assert isinstance(result, tuple) and len(result) == 2
    state, err = result
    assert isinstance(state, AgentState)
    assert isinstance(err, LimitExceededError)

    # Exactly one limits event emitted for this call
    events = _collect_limits_events(caplog.records[before:])
    assert len(events) == 1, f"expected 1 limits event, got {len(events)}: {events}"
    evt = events[0]
    assert evt.get("tool") == "limits" and evt.get("phase") == "error"
    assert evt.get("error_type") == "LimitExceededError"


@pytest.mark.asyncio
async def test_limits_event_before_raise(caplog, monkeypatch):
    # Offline by default via root env guard
    caplog.set_level(logging.INFO, logger="inspect_agents")
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    from inspect_ai.agent._agent import AgentState, agent
    from inspect_ai.model._chat_message import ChatMessageAssistant
    from inspect_ai.tool._tool_call import ToolCall

    from inspect_agents.agents import build_supervisor

    @agent
    def toy_submit_model2():
        async def execute(state: AgentState, tools):
            state.messages.append(
                ChatMessageAssistant(
                    content="",
                    tool_calls=[ToolCall(id="1", function="submit", arguments={"answer": "DONE"})],
                )
            )
            return state

        return execute

    agent_obj = build_supervisor(prompt="You are helpful.", tools=[], attempts=1, model=toy_submit_model2())

    from inspect_ai.util import LimitExceededError, time_limit

    from inspect_agents.run import run_agent

    before = len(caplog.records)
    with pytest.raises(LimitExceededError):
        await run_agent(
            agent_obj,
            "start",
            limits=[time_limit(0)],
            raise_on_limit=True,
        )

    # Exactly one limits event emitted for this call (prior to exception propagation)
    events = _collect_limits_events(caplog.records[before:])
    assert len(events) == 1, f"expected 1 limits event, got {len(events)}: {events}"
    evt = events[0]
    assert evt.get("tool") == "limits" and evt.get("phase") == "error"
    assert evt.get("error_type") == "LimitExceededError"
