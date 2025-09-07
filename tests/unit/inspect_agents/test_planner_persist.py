from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


def _repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "examples").exists() and (parent / "pyproject.toml").exists():
            return parent
    return p.parents[-1]


def _load_planner_module() -> object:
    repo_root = _repo_root()
    mod_path = repo_root / "examples" / "inspect" / "exploration" / "planner_tool.py"
    assert mod_path.exists(), f"Missing module at {mod_path}"
    spec = spec_from_file_location("planner_tool_for_persist", str(mod_path))
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod


@pytest.mark.asyncio
async def test_planner_plan_can_be_persisted_with_files_tool() -> None:
    # Arrange: build tools
    mod = _load_planner_module()
    planner = mod.planner_tool()

    from inspect_agents.tools import read_file, write_file

    wf = write_file()
    rf = read_file()

    # Act: generate plan and persist to plan.json in the Files store
    plan = await planner(prompt='Explore "Inspect-AI" patterns')
    payload = json.dumps(plan, ensure_ascii=False)
    await wf(file_path="plan.json", content=payload)

    # Assert: we can read it back and it contains the expected key
    content = await rf(file_path="plan.json")
    text = content if isinstance(content, str) else "\n".join(content.lines)
    assert '"queries"' in text or "queries" in text
