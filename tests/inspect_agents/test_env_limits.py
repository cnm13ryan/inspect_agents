import os
import sys
import types

import pytest


def _install_inspect_stubs(monkeypatch):
    """Install minimal Inspect stubs needed by build_subagents.

    Returns a dict bound to the handoff stub to inspect captured args per test.
    """
    captured: dict[str, object] = {}

    # agent._react.react
    mod_react = types.ModuleType("inspect_ai.agent._react")

    def react(**kwargs):
        return {"agent": kwargs}

    mod_react.react = react  # type: ignore[attr-defined]
    # Ensure cleanup via pytest's monkeypatch
    monkeypatch.setitem(sys.modules, "inspect_ai.agent._react", mod_react)

    # agent._as_tool.as_tool (not used in these tests but safe to stub)
    mod_as_tool = types.ModuleType("inspect_ai.agent._as_tool")

    def as_tool(agent, description=None):
        return {"as_tool": agent, "description": description}

    mod_as_tool.as_tool = as_tool  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "inspect_ai.agent._as_tool", mod_as_tool)

    # agent._handoff.handoff — capture limits
    mod_handoff = types.ModuleType("inspect_ai.agent._handoff")

    def handoff(agent, description, input_filter=None, output_filter=None, tool_name=None, limits=None):
        captured["agent"] = agent
        captured["description"] = description
        captured["tool_name"] = tool_name
        captured["limits"] = limits
        return {"handoff": tool_name, "limits": limits}

    mod_handoff.handoff = handoff  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "inspect_ai.agent._handoff", mod_handoff)

    return captured


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    # Ensure no lingering env from the developer shell interferes
    for k in list(os.environ.keys()):
        if (
            k.startswith("INSPECT_LIMIT_TIME__")
            or k.startswith("INSPECT_LIMIT_MESSAGES__")
            or k.startswith("INSPECT_LIMIT_TOKENS__")
        ):
            monkeypatch.delenv(k, raising=False)


def test_env_limits_apply_when_yaml_missing(monkeypatch):
    cap = _install_inspect_stubs(monkeypatch)
    # Set per-agent env: researcher → 8 messages
    monkeypatch.setenv("INSPECT_LIMIT_MESSAGES__researcher", "8")

    from inspect_agents.agents import build_subagents

    cfgs = [
        {
            "name": "researcher",
            "description": "web research agent",
            "prompt": "...",
            "mode": "handoff",
            # limits omitted on purpose
        }
    ]

    build_subagents(cfgs, base_tools=[])

    limits = cap.get("limits")
    assert isinstance(limits, list), "handoff should receive a list of limits from env"
    assert len(limits) == 1, "expected exactly one env-derived limit (messages=8)"


def test_env_limits_precedence_yaml_wins_nonempty(monkeypatch):
    cap = _install_inspect_stubs(monkeypatch)
    monkeypatch.setenv("INSPECT_LIMIT_MESSAGES__researcher", "8")

    from inspect_agents.agents import build_subagents

    sentinel = [object()]  # non-empty list should win over env
    cfgs = [
        {
            "name": "researcher",
            "description": "web research agent",
            "prompt": "...",
            "mode": "handoff",
            "limits": sentinel,
        }
    ]

    build_subagents(cfgs, base_tools=[])

    assert cap.get("limits") is sentinel, "non-empty YAML/programmatic limits must take precedence over env"


def test_env_suffix_normalization_variants(monkeypatch):
    cap = _install_inspect_stubs(monkeypatch)
    # Name normalization: "Research Assistant v2!" → "research_assistant_v2"
    monkeypatch.setenv("INSPECT_LIMIT_MESSAGES__research_assistant_v2", "7")

    from inspect_agents.agents import build_subagents

    cfgs = [
        {
            "name": "Research Assistant v2!",
            "description": "mixed chars",
            "prompt": "...",
            "mode": "handoff",
        }
    ]

    build_subagents(cfgs, base_tools=[])

    limits = cap.get("limits")
    assert isinstance(limits, list)
    assert len(limits) == 1, "expected one message limit via normalized suffix"
