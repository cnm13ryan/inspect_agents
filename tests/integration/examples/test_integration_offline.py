from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


def _load_planner_tool() -> object:
    repo_root = Path(__file__).resolve().parents[3]
    mod_path = repo_root / "examples" / "inspect" / "exploration" / "planner_tool.py"
    assert mod_path.exists(), f"Missing module at {mod_path}"
    spec = spec_from_file_location("planner_tool_local", str(mod_path))
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod


def _load_tools() -> object:
    # Import the installed package-style module so relative imports resolve
    import sys

    repo_root = Path(__file__).resolve().parents[3]
    src_dir = str(repo_root / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    import inspect_agents.tools as tools  # type: ignore

    return tools


@pytest.mark.parametrize("fs_mode", ["store", "sandbox"])  # run in both modes
@pytest.mark.asyncio
async def test_offline_planner_writes_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fs_mode: str) -> None:
    # Enforce offline and avoid web_search enablement
    monkeypatch.setenv("NO_NETWORK", "1")
    monkeypatch.delenv("INSPECT_ENABLE_WEB_SEARCH", raising=False)
    # Filesystem mode per Param
    if fs_mode == "sandbox":
        monkeypatch.setenv("INSPECT_AGENTS_FS_MODE", "sandbox")
        # Ensure we don't require a live sandbox; exercise fallback-to-store path
        monkeypatch.setenv("INSPECT_SANDBOX_PREFLIGHT", "skip")
    else:
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
    if isinstance(listing, list):
        names = set(listing)
    else:
        names = set(getattr(listing, "files", []))
    assert "plan.json" in names
    assert "question.txt" in names

    # Verify JSON structure by reading back
    content = await read_file(file_path="plan.json", limit=2000)
    raw_lines = content.splitlines() if isinstance(content, str) else list(getattr(content, "lines", []))
    # Strip legacy numbered prefixes like "   1\t" when typed results are disabled
    import re as _re

    clean_lines = [_re.sub(r"^\s*\d+\t", "", ln) for ln in raw_lines]
    text = "\n".join(clean_lines)
    data = json.loads(text)
    assert isinstance(data, dict)
    assert len(data.get("queries", [])) <= cfg["max_queries"]
    assert data.get("breadth") == cfg["breadth"] and data.get("depth") == cfg["depth"]
