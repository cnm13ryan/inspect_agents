from __future__ import annotations

"""Examples tool wrapper: deterministic exploration planner.

Surfaces QuerySpec items from the examples planner as a simple, JSON-friendly
structure for downstream web search tools. Offline and deterministic.
"""

from typing import Any, Dict, List


def _load_planner():
    """Import planner utilities with a path-based fallback.

    Avoids conflicts with a site-packages module named "examples".
    """
    try:
        # Normal relative imports when package layout is intact
        from .planner import ExplorationConfig, plan  # type: ignore
        from .config_loader import load_exploration_config  # type: ignore

        return ExplorationConfig, plan, load_exploration_config
    except Exception:  # pragma: no cover - fallback for REPL/tests
        import importlib.util
        import os
        from pathlib import Path

        here = Path(__file__).resolve()
        planner_path = here.with_name("planner.py")
        loader_path = here.with_name("config_loader.py")

        spec_planner = importlib.util.spec_from_file_location("_examples_planner", str(planner_path))
        mod_planner = importlib.util.module_from_spec(spec_planner)  # type: ignore[arg-type]
        assert spec_planner and spec_planner.loader
        spec_planner.loader.exec_module(mod_planner)  # type: ignore[union-attr]

        spec_loader = importlib.util.spec_from_file_location("_examples_cfg_loader", str(loader_path))
        mod_loader = importlib.util.module_from_spec(spec_loader)  # type: ignore[arg-type]
        assert spec_loader and spec_loader.loader
        spec_loader.loader.exec_module(mod_loader)  # type: ignore[union-attr]

        return mod_planner.ExplorationConfig, mod_planner.plan, mod_loader.load_exploration_config


def _merge_config(overrides: Dict[str, Any] | None, defaults: Any) -> Any:
    """Merge a plain dict of overrides into an ExplorationConfig instance.

    Only known fields are applied; unknown keys (except 'tags') are ignored.
    Returns a new ExplorationConfig object.
    """
    ExplorationConfig, _, _ = _load_planner()
    if not overrides:
        return defaults
    fields = {
        k: overrides[k]
        for k in [
            "breadth",
            "depth",
            "seed",
            "convergence_delta",
            "max_queries",
            "synonym_expansion",
            "site_hints",
        ]
        if k in overrides
    }
    data = defaults.model_dump() if hasattr(defaults, "model_dump") else defaults.__dict__
    data.update(fields)
    return ExplorationConfig(**data)


def _extra_tags(cfg: Dict[str, Any] | None) -> List[str]:
    if not cfg:
        return []
    t = cfg.get("tags")
    if not t:
        return []
    return [str(x) for x in (t if isinstance(t, list) else [t])]


def _build_result(items: List[Any], breadth: int, depth: int, extra_tags: List[str], max_queries: int) -> Dict[str, Any]:
    out: List[Dict[str, Any]] = []
    for it in items:
        # filter to depth >= 1 to avoid seed-only entries
        d = int(getattr(it, "depth", 0))
        if d < 1:
            continue
        q = getattr(it, "query", None)
        tags = list(getattr(it, "tags", []) or [])
        if extra_tags:
            # append without deduping aggressively to preserve determinism
            tags = tags + extra_tags
        out.append({"query": q, "depth": d, "tags": tags})
        if len(out) >= max_queries:
            break
    return {"breadth": breadth, "depth": depth, "queries": out}


def planner_tool():  # -> Tool
    """Return an Inspect‑AI Tool that plans exploration queries.

    Parameters
    - prompt: user prompt (string)
    - config: optional dict with ExplorationConfig fields and optional 'tags' (list[str])

    Returns
    - dict with keys: breadth, depth, queries (list of {query, depth, tags})
    """

    # Local import to avoid heavy imports at module import time
    from inspect_ai.tool._tool import tool
    from inspect_ai.tool._tool_def import ToolDef
    from inspect_ai.tool._tool_params import ToolParams

    ExplorationConfig, _plan, load_cfg = _load_planner()

    @tool(name="planner_tool")
    def planner_tool_factory():  # -> Tool
        async def execute(prompt: str, config: Dict[str, Any] | None = None) -> Dict[str, Any]:
            # Load defaults from YAML (if available), else use code defaults
            try:
                base = load_cfg(None)
            except Exception:
                base = ExplorationConfig()  # type: ignore[call-arg]

            cfg = _merge_config(config, base)
            items = _plan(prompt, cfg)
            return _build_result(
                items=items,
                breadth=int(getattr(cfg, "breadth", 0)),
                depth=int(getattr(cfg, "depth", 0)),
                extra_tags=_extra_tags(config),
                max_queries=int(getattr(cfg, "max_queries", len(items))),
            )

        # Hint for tests that introspect the returned callable
        try:
            setattr(execute, "name", "planner_tool")
            execute.__name__ = "planner_tool"  # type: ignore[attr-defined]
        except Exception:
            pass
        return execute

    return planner_tool_factory()
