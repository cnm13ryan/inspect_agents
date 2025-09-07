import importlib.util
import os


def _load_planner():
    """Load the planner module by file path to avoid site-packages 'examples' conflicts."""
    path = os.path.join(os.getcwd(), "examples/inspect/exploration/planner.py")
    spec = importlib.util.spec_from_file_location("examples.inspect.exploration.planner", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_classify_prompt_fresh_vs_evergreen():
    planner = _load_planner()
    assert planner.classify_prompt("Latest AI in 2025") == "fresh"
    assert planner.classify_prompt("Overview of sorting algorithms") == "evergreen"


def test_generate_seed_queries_respects_breadth_and_contains_base():
    planner = _load_planner()
    exploration_config = planner.ExplorationConfig
    cfg = exploration_config(breadth=3, depth=0, seed=1, site_hints=["arxiv.org", "*.gov"])  # enough variety
    seeds = planner.generate_seed_queries("AI ranking methods", cfg)
    # Base query should be present and list length bounded by breadth
    assert any(s.query == "AI ranking methods" and s.depth == 0 for s in seeds)
    assert len(seeds) <= cfg.breadth


def test_plan_limits_count_and_depth():
    planner = _load_planner()
    exploration_config = planner.ExplorationConfig
    cfg = exploration_config(breadth=3, depth=1, seed=7, max_queries=6, site_hints=["arxiv.org", "*.edu"])
    items = planner.plan("Latest AI research on LLM ranking", cfg)
    assert 1 <= len(items) <= 6
    assert max(i.depth for i in items) <= 1


def test_plan_is_deterministic_with_seed_changes_order_with_different_seed():
    planner = _load_planner()
    exploration_config = planner.ExplorationConfig
    prompt = "Latest AI research on LLM ranking"
    cfg1 = exploration_config(breadth=3, depth=1, seed=42, max_queries=8, site_hints=["arxiv.org", "*.gov", "*.edu"])
    cfg2 = exploration_config(breadth=3, depth=1, seed=43, max_queries=8, site_hints=["arxiv.org", "*.gov", "*.edu"])
    a = [q.query for q in planner.plan(prompt, cfg1)]
    b = [q.query for q in planner.plan(prompt, cfg1)]
    c = [q.query for q in planner.plan(prompt, cfg2)]
    assert a == b  # same seed → identical
    assert a != c  # different seed → order/selection can differ


def test_seed_dedupes_duplicate_site_hints():
    planner = _load_planner()
    exploration_config = planner.ExplorationConfig
    cfg = exploration_config(
        breadth=4, depth=0, seed=0, site_hints=["arxiv.org", "https://arxiv.org", "www.arxiv.org"]
    )  # duplicates
    seeds = planner.generate_seed_queries("transformer architecture", cfg)
    # Only one site:arxiv.org variant expected after dedupe
    site_variants = [s for s in seeds if s.query.startswith("site:arxiv.org ")]
    assert len(site_variants) == 1

    # YAML loader tests are in test_exploration_loader.py
