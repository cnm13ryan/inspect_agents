from __future__ import annotations

import asyncio
import json
import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


def _load_planner_tool() -> object:
    repo_root = Path(__file__).resolve().parents[2]
    mod_path = repo_root / "examples" / "inspect" / "exploration" / "planner_tool.py"
    assert mod_path.exists(), f"Missing module at {mod_path}"
    spec = spec_from_file_location("planner_tool_local", str(mod_path))
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod


def _load_tools() -> object:
    repo_root = Path(__file__).resolve().parents[2]
    mod_path = repo_root / "src" / "inspect_agents" / "tools.py"
    assert mod_path.exists(), f"Missing module at {mod_path}"
    spec = spec_from_file_location("inspect_agents_tools", str(mod_path))
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod


@pytest.mark.asyncio
async def test_offline_planner_writes_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Enforce offline and avoid web_search enablement
    monkeypatch.setenv("NO_NETWORK", "1")
    monkeypatch.delenv("INSPECT_ENABLE_WEB_SEARCH", raising=False)
    # Keep default in-memory Store mode (no sandbox writes to host FS)
    monkeypatch.delenv("INSPECT_AGENTS_FS_MODE", raising=False)

    tools_mod = _load_tools()
    planner_mod = _load_planner_tool()

    planner = planner_mod.planner_tool()
    write_file = tools_mod.write_file()
    ls = tools_mod.ls()
    read_file = tools_mod.read_file()

    prompt = "Explore Inspect-AI agent patterns"
    cfg = {"max_queries": 6, "breadth": 3, "depth": 2, "tags": ["integration"]}

    # Execute planner tool
    plan = await planner(prompt=prompt, config=cfg)
    assert isinstance(plan, dict) and "queries" in plan
    assert len(plan["queries"]) <= cfg["max_queries"]
    assert plan["breadth"] == cfg["breadth"] and plan["depth"] == cfg["depth"]

    # Write artifacts via tools into the in-memory Files store
    await write_file(file_path="plan.json", content=json.dumps(plan, indent=2))
    await write_file(file_path="question.txt", content=prompt)

    # Verify presence via ls tool
    listing = await ls()
    files = getattr(listing, "files", []) if hasattr(listing, "files") else []
    names = [f.get("path") if isinstance(f, dict) else getattr(f, "path", None) for f in files]
    assert "plan.json" in set(names)
    assert "question.txt" in set(names)

    # Verify JSON structure by reading back
    content = await read_file(file_path="plan.json", limit=2000)
    text = content if isinstance(content, str) else "\n".join(getattr(content, "lines", []))
    data = json.loads(text)
    assert isinstance(data, dict)
    assert len(data.get("queries", [])) <= cfg["max_queries"]
    assert data.get("breadth") == cfg["breadth"] and data.get("depth") == cfg["depth"]
