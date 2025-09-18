import asyncio

import pytest
from inspect_ai.agent._agent import AgentState, agent
from inspect_ai.model._chat_message import ChatMessageAssistant, ChatMessageUser
from inspect_ai.tool._tool_call import ToolCall

from inspect_agents.agents import build_supervisor
from inspect_agents.tools import read_file


@agent
def toy_submit_model():
    async def execute(state: AgentState, tools):
        # Immediately call submit with a final answer
        state.messages.append(
            ChatMessageAssistant(
                content="", tool_calls=[ToolCall(id="1", function="submit", arguments={"answer": "DONE"})]
            )
        )
        return state

    return execute


def test_supervisor_runs_and_submits():
    # Build supervisor with toy model that always submits
    agent = build_supervisor(prompt="You are helpful.", tools=[], attempts=1, model=toy_submit_model())

    # Kick off with a user message
    state = AgentState(messages=[ChatMessageUser(content="start")])

    result = asyncio.run(agent(state))

    # Completion should include the submitted answer
    assert "DONE" in (result.output.completion or "")


@pytest.mark.parametrize(
    ("include_defaults", "tool_factory", "expected_count"),
    [
        (True, lambda: [], 0),
        (False, lambda: [read_file()], 1),
    ],
)
def test_supervisor_emits_defaults_telemetry(monkeypatch, include_defaults, tool_factory, expected_count):
    events: list[dict[str, object]] = []

    def _capture(name, phase, args=None, extra=None, t0=None):
        events.append({"name": name, "phase": phase, "args": args, "extra": extra})
        return 0.0 if t0 is None else t0

    monkeypatch.setattr("inspect_agents.observability.log_tool_event", _capture)

    build_supervisor(prompt="You are helpful.", tools=tool_factory(), include_defaults=include_defaults)

    telemetry = [ev for ev in events if ev["name"] == "agent_defaults"]
    assert telemetry, "expected agent_defaults telemetry"

    record = telemetry[-1]
    extra = record["extra"] or {}
    assert extra["builder"] == "supervisor"
    assert extra["include_defaults"] is include_defaults
    assert extra["include_defaults_source"] == "explicit"
    assert extra["caller_supplied_tool_count"] == expected_count
    assert extra["caller_supplied_replacements"] is bool(expected_count)
    assert extra["feature_flag"] == "INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS"
    assert extra["feature_flag_state"] == "unset"
    assert extra["active_tool_count"] >= expected_count


@pytest.mark.parametrize(
    ("env_value", "expected_default"),
    [
        ("0", False),
        ("1", True),
        ("no", False),
    ],
)
def test_supervisor_include_defaults_env(monkeypatch, env_value, expected_default):
    events: list[dict[str, object]] = []

    def _capture(name, phase, args=None, extra=None, t0=None):
        events.append({"name": name, "phase": phase, "args": args, "extra": extra})
        return 0.0 if t0 is None else t0

    monkeypatch.setattr("inspect_agents.observability.log_tool_event", _capture)
    monkeypatch.setenv("INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS", env_value)

    build_supervisor(prompt="You are helpful.")

    telemetry = [ev for ev in events if ev["name"] == "agent_defaults"]
    assert telemetry, "expected agent_defaults telemetry"

    record = telemetry[-1]
    extra = record["extra"] or {}
    assert extra["builder"] == "supervisor"
    assert extra["include_defaults"] is expected_default
    assert extra["include_defaults_source"] == "env"
    assert extra["feature_flag_state"] == env_value
    assert extra["active_tool_count"] >= (1 if expected_default else 0)


def test_supervisor_include_defaults_env_can_be_overridden(monkeypatch):
    events: list[dict[str, object]] = []

    def _capture(name, phase, args=None, extra=None, t0=None):
        events.append({"name": name, "phase": phase, "args": args, "extra": extra})
        return 0.0 if t0 is None else t0

    monkeypatch.setattr("inspect_agents.observability.log_tool_event", _capture)
    monkeypatch.setenv("INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS", "0")

    build_supervisor(prompt="Explicit wins", include_defaults=True)

    telemetry = [ev for ev in events if ev["name"] == "agent_defaults"]
    assert telemetry, "expected agent_defaults telemetry"

    record = telemetry[-1]
    extra = record["extra"] or {}
    assert extra["include_defaults"] is True
    assert extra["include_defaults_source"] == "explicit"
    assert extra["feature_flag_state"] == "0"
