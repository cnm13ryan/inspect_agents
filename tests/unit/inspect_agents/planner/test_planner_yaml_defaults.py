from __future__ import annotations

import json
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")  # ensure PyYAML is available for this test


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
    spec = spec_from_file_location("planner_tool_yaml_defaults", str(mod_path))
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod


@pytest.mark.asyncio
async def test_planner_uses_yaml_defaults_when_config_none() -> None:
    # Purge potentially polluted modules from earlier tests that monkeypatch loader
    # Drop specific entries and any lingering examples.inspect.exploration.* modules
    purge_list = [
        "examples.inspect.exploration.planner_tool",
        "examples.inspect.exploration.planner",
        "examples.inspect.exploration.config_loader",
        "examples.lib.exploration.planner_tool",
        "examples.lib.exploration.planner",
        "examples.lib.exploration.config_loader",
        "_examples_planner",
        "_examples_cfg_loader",
    ]
    for name in list(sys.modules.keys()):
        if name in purge_list or name.startswith("examples.inspect.exploration"):
            sys.modules.pop(name, None)

    # Ensure the example YAML exists
    repo_root = _repo_root()
    yaml_path = repo_root / "examples" / "configs" / "research" / "exploration.yaml"
    assert yaml_path.exists(), f"expected defaults YAML at {yaml_path}"

    # Load tool and invoke with config=None in a fresh subprocess to avoid
    # any in-process monkeypatch/closure leakage from prior tests
    repo_root = _repo_root()
    mod_path = repo_root / "examples" / "inspect" / "exploration" / "planner_tool.py"
    prompt_literal = repr('Explore "Inspect-AI" patterns')
    code = "\n".join(
        [
            "import asyncio, json",
            "from importlib.util import spec_from_file_location, module_from_spec",
            f"p = r'{str(mod_path)}'",
            "spec = spec_from_file_location('planner_tool_isolated', p)",
            "m = module_from_spec(spec)",
            "spec.loader.exec_module(m)",
            "async def run():",
            "    t = m.planner_tool()",
            f"    r = await t(prompt={prompt_literal}, config=None)",
            "    print(json.dumps(r))",
            "asyncio.run(run())",
        ]
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    # Take the last non-empty line (ignore deprecation warnings to stderr)
    stdout_lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert stdout_lines, f"no output from subprocess: stdout='{proc.stdout}', stderr='{proc.stderr}'"
    result = json.loads(stdout_lines[-1])

    # Values derived from examples/configs/research/exploration.yaml (policy.*)
    with yaml_path.open("r", encoding="utf-8") as f:
        y = yaml.safe_load(f) or {}
    policy = (y.get("policy") or {}) if isinstance(y, dict) else {}
    expected_breadth = int(policy.get("breadth", -1))
    expected_depth = int(policy.get("depth", -1))
    expected_max = int(policy.get("max_queries", -1))

    assert result["breadth"] == expected_breadth
    assert result["depth"] == expected_depth
    # The tool must not exceed the YAML cap; it may return fewer
    assert 0 < len(result["queries"]) <= expected_max
