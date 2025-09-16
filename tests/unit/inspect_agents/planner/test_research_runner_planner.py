from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "examples").exists() and (parent / "pyproject.toml").exists():
            return parent
    return p.parents[-1]


def _load_runner_module():
    repo_root = _repo_root()
    mod_path = repo_root / "examples" / "runners" / "research_runner.py"
    assert mod_path.exists(), f"Missing runner at {mod_path}"
    spec = spec_from_file_location("research_runner_local", str(mod_path))
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod


def test_runner_exposes_planner_tool():
    mod = _load_runner_module()
    # Ensure helper exists and returns a tool with the expected name when file is present
    assert hasattr(mod, "_load_planner_tool"), "runner should expose _load_planner_tool()"
    tool_obj = mod._load_planner_tool()
    assert tool_obj is not None, "planner tool failed to load"
    name = getattr(tool_obj, "name", None) or getattr(tool_obj, "__name__", None)
    assert name == "planner_tool"
