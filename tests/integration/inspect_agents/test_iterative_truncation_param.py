import asyncio

import pytest
from inspect_ai.model._chat_message import ChatMessageAssistant, ChatMessageSystem, ChatMessageUser
from inspect_ai.model._model import Model
from inspect_ai.model._model_output import ModelOutput
from inspect_ai.tool._tool_def import ToolDef
from inspect_ai.tool._tool_params import ToolParams

from inspect_agents.iterative import build_iterative_agent
from inspect_agents.tools import read_file

pytestmark = pytest.mark.truncation


def long_output_tool():
    async def execute() -> str:
        # Return an output well above 10 KiB to exercise truncation
        return "x" * (20 * 1024)

    params = ToolParams()
    return ToolDef(execute, name="long_output", description="returns long text", parameters=params).as_tool()


class OneCallToolModel(Model):
    async def generate(self, input, tools, config, cache: bool = False):
        # Always request our long_output tool
        return ModelOutput.from_message(
            ChatMessageAssistant(
                content="",
                tool_calls=[{"id": "1", "function": "long_output", "arguments": {}}],
                source="generate",
            )
        )


def _run(agent, state):
    return asyncio.run(agent(state))


def test_iterative_param_caps_tool_output(monkeypatch):
    # Ensure env does not interfere; rely on explicit param precedence
    monkeypatch.delenv("INSPECT_MAX_TOOL_OUTPUT", raising=False)

    # Build agent with explicit 4 KiB cap passed as parameter
    tool = long_output_tool()
    agent = build_iterative_agent(
        model=OneCallToolModel.__new__(OneCallToolModel),
        tools=[tool],
        max_steps=1,
        max_tool_output_bytes=4096,
    )

    # Seed conversation with a system + user
    from inspect_ai.agent._agent import AgentState

    state = AgentState(messages=[ChatMessageSystem(content="sys"), ChatMessageUser(content="start")])

    new_state = _run(agent, state)

    # Locate tool message
    from inspect_ai.model._chat_message import ChatMessageTool

    tool_msgs = [m for m in new_state.messages if isinstance(m, ChatMessageTool)]
    assert tool_msgs, "Expected a tool message from long_output"

    tm = tool_msgs[0]
    # Tool content can be a string or list of Content; normalize to text
    if isinstance(tm.content, str):
        text = tm.content
    else:
        text = "".join([getattr(c, "text", "") for c in tm.content])

    # Assert envelope present and payload length equals the configured cap
    assert "The output of your call to long_output was too long to be displayed." in text
    assert "<START_TOOL_OUTPUT>" in text and "<END_TOOL_OUTPUT>" in text

    start = text.index("<START_TOOL_OUTPUT>") + len("<START_TOOL_OUTPUT>")
    end = text.index("<END_TOOL_OUTPUT>")
    payload = text[start:end].strip("\n")
    assert len(payload.encode("utf-8")) == 4096


@pytest.mark.parametrize(
    ("include_defaults", "tool_factory", "expected_count"),
    [
        (True, lambda: [], 0),
        (False, lambda: [read_file()], 1),
    ],
)
def test_iterative_emits_defaults_telemetry(monkeypatch, include_defaults, tool_factory, expected_count):
    events: list[dict[str, object]] = []

    def _capture(name, phase, args=None, extra=None, t0=None):
        events.append({"name": name, "phase": phase, "args": args, "extra": extra})
        return 0.0 if t0 is None else t0

    monkeypatch.setattr("inspect_agents.observability.log_tool_event", _capture)

    build_iterative_agent(
        prompt="Instrument defaults",
        tools=tool_factory(),
        include_defaults=include_defaults,
        max_steps=1,
    )

    telemetry = [ev for ev in events if ev["name"] == "agent_defaults"]
    assert telemetry, "expected agent_defaults telemetry"

    record = telemetry[-1]
    extra = record["extra"] or {}
    assert extra["builder"] == "iterative"
    assert extra["include_defaults"] is include_defaults
    assert extra["include_defaults_source"] == "explicit"
    assert extra["caller_supplied_tool_count"] == expected_count
    assert extra["caller_supplied_replacements"] is bool(expected_count)
    assert extra["feature_flag"] == "INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS"
    assert extra["feature_flag_state"] == "unset"
    assert extra["active_tool_count"] >= expected_count
    assert isinstance(extra.get("code_only"), bool)


@pytest.mark.parametrize(
    ("env_value", "expected_default"),
    [
        ("0", False),
        ("1", True),
    ],
)
def test_iterative_include_defaults_env(monkeypatch, env_value, expected_default):
    events: list[dict[str, object]] = []

    def _capture(name, phase, args=None, extra=None, t0=None):
        events.append({"name": name, "phase": phase, "args": args, "extra": extra})
        return 0.0 if t0 is None else t0

    monkeypatch.setattr("inspect_agents.observability.log_tool_event", _capture)
    monkeypatch.setenv("INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS", env_value)

    build_iterative_agent(prompt="Env override", tools=[], max_steps=1)

    telemetry = [ev for ev in events if ev["name"] == "agent_defaults"]
    assert telemetry, "expected agent_defaults telemetry"

    record = telemetry[-1]
    extra = record["extra"] or {}
    assert extra["builder"] == "iterative"
    assert extra["include_defaults"] is expected_default
    assert extra["include_defaults_source"] == "env"
    assert extra["feature_flag_state"] == env_value
    assert extra["active_tool_count"] >= (1 if expected_default else 0)


def test_iterative_include_defaults_env_can_be_overridden(monkeypatch):
    events: list[dict[str, object]] = []

    def _capture(name, phase, args=None, extra=None, t0=None):
        events.append({"name": name, "phase": phase, "args": args, "extra": extra})
        return 0.0 if t0 is None else t0

    monkeypatch.setattr("inspect_agents.observability.log_tool_event", _capture)
    monkeypatch.setenv("INSPECT_AGENTS_INCLUDE_DEFAULT_TOOLS", "0")

    build_iterative_agent(prompt="Explicit", include_defaults=True, max_steps=1)

    telemetry = [ev for ev in events if ev["name"] == "agent_defaults"]
    assert telemetry, "expected agent_defaults telemetry"

    record = telemetry[-1]
    extra = record["extra"] or {}
    assert extra["include_defaults"] is True
    assert extra["include_defaults_source"] == "explicit"
    assert extra["feature_flag_state"] == "0"
