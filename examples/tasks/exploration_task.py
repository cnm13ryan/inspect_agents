#!/usr/bin/env python3
"""
Inspect task wrapper for the exploration composition (so `inspect eval` works).

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

from inspect_ai import Task, task
from inspect_ai.dataset import Sample

from examples.lib.builders import build_exploration_supervisor
from examples.lib.exploration.config_loader import load_exploration_sections
from inspect_agents.model import resolve_model


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

    # Load optional YAML: (policy → planner_cfg, supervisor → prompts/attempts)
    planner_cfg, _scoring_cfg, supervisor_cfg = load_exploration_sections(policy_config)

    # Attempts can be overridden from YAML supervisor.attempts
    yaml_attempts = None
    if supervisor_cfg and isinstance(supervisor_cfg.get("attempts"), int):
        yaml_attempts = int(supervisor_cfg["attempts"])
    eff_attempts = yaml_attempts if yaml_attempts is not None else int(attempts)

    # Optional prompt overrides under supervisor.prompts
    prompts = None
    if supervisor_cfg and isinstance(supervisor_cfg.get("prompts"), dict):
        raw = supervisor_cfg["prompts"]
        prompts = {str(k): str(v) for k, v in raw.items()}

    # Build the composed agent via shared builder (includes planner tool)
    agent = build_exploration_supervisor(
        model=model_id,
        attempts=eff_attempts,
        planner_cfg=planner_cfg,
        prompts_override=prompts,
    )

    return Task(
        dataset=[Sample(input=prompt)],
        solver=agent,
    )
