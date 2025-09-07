from __future__ import annotations

from pathlib import Path

import pytest


def _import_planner_and_tool():
    import importlib
    import sys

    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    planner = importlib.import_module("examples.inspect.exploration.planner")
    toolmod = importlib.import_module("examples.inspect.exploration.planner_tool")
    return planner, toolmod


@pytest.mark.asyncio
async def test_planner_tool_uses_yaml_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    planner, toolmod = _import_planner_and_tool()

    # Policy values we expect to propagate into tool output when config=None
    policy = dict(max_queries=4, breadth=2, depth=1, seed=0)

    # Monkeypatch the tool's internal loader to return our policy via ExplorationConfig
    def _stub_loader(_path: str | None = None):  # type: ignore[no-untyped-def]
        return planner.ExplorationConfig(**policy)

    def _stub_load_planner():  # type: ignore[no-untyped-def]
        return planner.ExplorationConfig, planner.plan, _stub_loader

    monkeypatch.setattr(toolmod, "_load_planner", _stub_load_planner)

    # Build the tool and call without explicit config so it uses the loader
    tool = toolmod.planner_tool()
    result = await tool(prompt="Explore Inspect-AI", config=None)

    assert isinstance(result, dict)
    assert result.get("breadth") == policy["breadth"]
    assert result.get("depth") == policy["depth"]
    assert len(result.get("queries", [])) <= policy["max_queries"]
