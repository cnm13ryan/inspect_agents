from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


def _load_planner() -> object:
    repo_root = Path(__file__).resolve().parents[3]
    mod_path = repo_root / "examples" / "inspect" / "exploration" / "planner.py"
    assert mod_path.exists(), f"Missing module at {mod_path}"
    spec = spec_from_file_location("examples_planner", str(mod_path))
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


@pytest.mark.parametrize(
    "prompt,expected_class",
    [
        ("Latest LLM benchmarks in 2024", "fresh"),
        ("History of page ranking algorithms", "evergreen"),
    ],
)
def test_plan_bounds_and_tags(prompt: str, expected_class: str) -> None:
    mod = _load_planner()
    # Seeded + bounded config
    cfg = mod.ExplorationConfig(breadth=4, depth=3, seed=42, max_queries=12)

    items = mod.plan(prompt, cfg)

    # Size bound
    assert len(items) <= cfg.max_queries
    assert len(items) > 0

    # Depth bounds
    assert all(0 <= it.depth <= cfg.depth for it in items)

    # Diversity: at least min(3, breadth) distinct normalized queries
    uniq = {_norm(it.query) for it in items}
    assert len(uniq) >= min(3, cfg.breadth)

    # Classification tag appears on at least one item
    tags = {t for it in items for t in it.tags}
    assert expected_class in tags
