from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")  # ensure PyYAML is available for this test


def _load_planner_module() -> object:
    repo_root = Path(__file__).resolve().parents[2]
    mod_path = repo_root / "examples" / "inspect" / "exploration" / "planner_tool.py"
    assert mod_path.exists(), f"Missing module at {mod_path}"
    spec = spec_from_file_location("planner_tool_yaml_defaults", str(mod_path))
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod


@pytest.mark.asyncio
async def test_planner_uses_yaml_defaults_when_config_none() -> None:
    # Ensure the example YAML exists
    repo_root = Path(__file__).resolve().parents[2]
    yaml_path = repo_root / "examples" / "configs" / "research" / "exploration.yaml"
    assert yaml_path.exists(), f"expected defaults YAML at {yaml_path}"

    # Load tool and invoke with config=None
    mod = _load_planner_module()
    tool = mod.planner_tool()
    result = await tool(prompt='Explore "Inspect-AI" patterns', config=None)

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
