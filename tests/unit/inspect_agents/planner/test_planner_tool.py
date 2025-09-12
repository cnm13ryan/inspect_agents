from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


def _repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "examples").exists() and (parent / "pyproject.toml").exists():
            return parent
    return p.parents[-1]


def _load_local_module() -> object:
    # Load the planner tool module by absolute path to avoid any site-packages
    # conflicts with a top-level "examples" package name.
    repo_root = _repo_root()
    mod_path = repo_root / "examples" / "inspect" / "exploration" / "planner_tool.py"
    assert mod_path.exists(), f"Missing module at {mod_path}"

    spec = spec_from_file_location("planner_tool_local", str(mod_path))
    assert spec is not None and spec.loader is not None
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod


@pytest.mark.asyncio
async def test_planner_tool_returns_expected_structure() -> None:
    mod = _load_local_module()
    tool = mod.planner_tool()

    prompt = 'Plan an exploration for "Inspect-AI" use cases'
    cfg = {"max_queries": 5, "breadth": 2, "depth": 2, "tags": ["unit"]}

    result = await tool(prompt=prompt, config=cfg)

    # Top-level structure
    assert isinstance(result, dict)
    assert "queries" in result and isinstance(result["queries"], list)
    assert "breadth" in result and result["breadth"] == 2
    assert "depth" in result and result["depth"] == 2

    # Size bound
    assert len(result["queries"]) <= 5
    assert len(result["queries"]) > 0

    # Element structure
    for item in result["queries"]:
        assert set(item.keys()) == {"query", "depth", "tags"}
        assert isinstance(item["query"], str) and item["query"].strip()
        assert isinstance(item["depth"], int) and item["depth"] >= 1
        assert isinstance(item["tags"], list)
        assert all(isinstance(t, str) for t in item["tags"])
