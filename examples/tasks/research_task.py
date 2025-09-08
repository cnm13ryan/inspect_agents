#!/usr/bin/env python3
"""
Inspect task wrapper for the research composition (so `inspect eval` works here).

Usage
- uv run inspect eval examples/tasks/research_task.py \
  -T prompt="Curate a list of arXiv papers that Quantinuum published in 2025"

Options
- -T config="examples/configs/research/supervisor.yaml"  # load YAML composition
- -T enable_web_search=true                   # enable standard web_search tool

Environment
- INSPECT_ENABLE_WEB_SEARCH=1 TAVILY_API_KEY=... (or GOOGLE_CSE_* keys)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample

from examples.lib.builders import build_research_supervisor
from inspect_agents.config import load_and_build
from inspect_agents.model import resolve_model


def _load_examples_utils():
    """Best-effort import of examples._utils with path fallback.

    Uses repository-local examples/_utils.py to avoid collisions with any
    site-packages module named "examples". Returns the loaded module or None.
    """
    try:  # Prefer normal import when the local package layout is active
        from examples import _utils as _utils_mod  # type: ignore

        return _utils_mod
    except Exception:
        # Fallback to path-based import to avoid site-packages collisions
        import importlib.util as _il

        util_path = Path(__file__).resolve().parents[1] / "_utils.py"
        spec = _il.spec_from_file_location("_examples_utils_local", str(util_path))
        if spec is None or spec.loader is None:  # pragma: no cover - defensive
            return None
        mod = _il.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[arg-type]
        return mod  # type: ignore[return-value]


# Local helper to load the examples planner tool via import_by_path to avoid
# collisions with any site-packages module named "examples".
# (Note): planner tool inclusion is handled by the shared builder


@task
def research_task(
    prompt: str = "Write a short overview of Inspect‑AI",
    attempts: int = 1,
    config: str | None = None,
    enable_web_search: bool = False,
    write_plan: bool = False,
    plan_out: str = "plan.json",
):
    """Expose the research composition as an Inspect task.

    Mirrors the composition used by `examples/runners/research_runner.py`.
    Pass `config` to load a YAML composition; otherwise use the inline default.
    """

    # Optional tool toggle via task parameter (mirrors env behavior)
    if enable_web_search:
        os.environ["INSPECT_ENABLE_WEB_SEARCH"] = "1"

    model_id = resolve_model()

    # Optional: pre-plan and write plan.json using the examples planner (offline, deterministic)
    if write_plan:
        try:
            # Load planner API by path using centralized helper
            _utils = _load_examples_utils()
            if _utils is None:
                raise RuntimeError("Unable to load examples._utils")
            base = Path(__file__).resolve().parents[1] / "inspect" / "exploration"
            mod_p = _utils.import_by_path("_examples_planner", base / "planner.py")
            mod_c = _utils.import_by_path("_examples_cfg_loader", base / "config_loader.py")
            cfg = mod_c.load_exploration_config(None)
            items = mod_p.plan(prompt, cfg)
            # Build JSON like planner_tool (filter out seeds depth<1)
            q = []
            for it in items:
                d = int(getattr(it, "depth", 0))
                if d < 1:
                    continue
                q.append(
                    {
                        "query": getattr(it, "query", ""),
                        "depth": d,
                        "tags": list(getattr(it, "tags", []) or []),
                    }
                )
                if len(q) >= int(getattr(cfg, "max_queries", len(items))):
                    break
            result = {"breadth": int(cfg.breadth), "depth": int(cfg.depth), "queries": q}
            Path(plan_out).write_text(json.dumps(result, indent=2))
        except Exception:
            # Best-effort: ignore planning errors so the task still runs
            pass

    if config:
        # Build from YAML (returns: agent, tools, approvals, limits)
        # Accept any future extensions by using starred unpacking.
        agent, *_ = load_and_build(config, model=model_id)
    else:
        # Use shared builder (prompts/tool lists preserved, include planner tool)
        agent = build_research_supervisor(
            model=model_id,
            attempts=attempts,
            include_planner=True,
        )

    return Task(
        dataset=[Sample(input=prompt)],
        solver=agent,
    )
