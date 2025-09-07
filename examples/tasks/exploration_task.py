#!/usr/bin/env python3
"""
Inspect task wrapper for the exploration runner (so `inspect eval` works).

Usage
- uv run inspect eval examples/tasks/exploration_task.py \
  -T policy_config=examples/configs/research/exploration.yaml \
  -T prompt="Investigate <topic>; include sources" -T attempts=5

Options
- -T policy_config="examples/configs/research/exploration.yaml"  # YAML policy (breadth/depth/max_queries, etc.)
- -T enable_web_search=true                                   # enable standard web_search tool

Environment
- INSPECT_ENABLE_WEB_SEARCH=1 TAVILY_API_KEY=... (or GOOGLE_CSE_* keys)
"""

from __future__ import annotations

import os
from typing import Any
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample

from inspect_agents.model import resolve_model

# Reuse the runner wiring to construct the agent
def _load_runner_module():
    """Load the examples runner module by absolute path.

    Avoids requiring `examples` to be a Python package when running via file path.
    """
    repo_root = Path(__file__).resolve().parents[2]
    mod_path = repo_root / "examples" / "inspect" / "exploration" / "runner.py"
    assert mod_path.exists(), f"Missing runner at {mod_path}"
    spec = spec_from_file_location("examples_exploration_runner", str(mod_path))
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod


@task
def exploration_task(
    prompt: str = "Write a short overview of Inspect‑AI exploration",
    attempts: int = 3,
    policy_config: str | None = None,
    enable_web_search: bool = False,
):
    """Expose the exploration composition as an Inspect task.

    Reads optional YAML policy and hands it to the planner via the supervisor.
    """

    # Optional tool toggle via task parameter (mirrors env behavior)
    if enable_web_search:
        os.environ["INSPECT_ENABLE_WEB_SEARCH"] = "1"

    model_id: Any = resolve_model()

    # Load runner helpers by path to avoid package import constraints
    runner = _load_runner_module()

    # Load optional planner policy (YAML → dict)
    planner_cfg = runner._load_planner_config(policy_config)

    # Build the composed agent (supervisor + planner tool + handoffs)
    agent = runner.build_runner_agent(
        planner_cfg=planner_cfg,
        attempts=attempts,
        model=model_id,
    )

    return Task(
        dataset=[Sample(input=prompt)],
        solver=agent,
    )
