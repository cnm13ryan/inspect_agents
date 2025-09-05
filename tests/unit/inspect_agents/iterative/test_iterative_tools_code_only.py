import asyncio
from collections.abc import Sequence
from types import SimpleNamespace

from inspect_ai.agent._agent import AgentState
from inspect_ai.model._chat_message import (
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageUser,
)
from inspect_ai.model._model import Model
from inspect_ai.model._model_output import ModelOutput


class LSRequestModel(Model):
    async def generate(self, input, tools, config, cache: bool = False):  # noqa: ARG002
        # Always ask to call the built-in ls tool
        return ModelOutput.from_message(
            ChatMessageAssistant(
                content="",
                tool_calls=[{"id": "1", "function": "ls", "arguments": {}}],
                source="generate",
            )
        )


def test_code_only_exposes_only_fs_tools(monkeypatch):
    # Capture tool names the agent passes into execute_tools
    captured: dict[str, Sequence[str]] = {"names": []}

    # tool_defs() resolves Tool objects to ToolDef for introspection
    from inspect_ai.tool._tool_def import tool_defs

    async def fake_execute_tools(messages, tools, max_output=None):  # noqa: ARG001
        defs = await tool_defs(tools)
        captured["names"] = [td.name for td in defs]
        # Return minimal result structure the agent expects
        return SimpleNamespace(messages=[], output=None)

    # Patch before building the agent so the local import captures the stub
    monkeypatch.setattr(
        "inspect_ai.model._call_tools.execute_tools",
        fake_execute_tools,
        raising=True,
    )

    from inspect_agents.iterative import build_iterative_agent

    agent = build_iterative_agent(
        model=LSRequestModel.__new__(LSRequestModel),
        max_steps=1,
        code_only=True,
        # Deterministic time so remaining budget calculations don't matter here
        clock=lambda: 0.0,
    )

    state = AgentState(messages=[ChatMessageSystem(content="sys"), ChatMessageUser(content="start")])
    _ = asyncio.run(agent(state))

    # Expect only the FS tools to be present when code_only=True
    names = list(captured["names"])  # convert to list for stable asserts
    assert names, "Expected execute_tools to be invoked with some tools"

    expected = {"write_file", "read_file", "ls", "edit_file"}
    assert set(names) == expected, f"Expected only FS tools {expected}, got {set(names)}"
