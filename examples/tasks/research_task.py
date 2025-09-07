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

import os
import json
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample

from inspect_agents.agents import build_subagents, build_supervisor
from inspect_agents.config import load_and_build
from inspect_agents.model import resolve_model
from inspect_agents.tools import (
    edit_file,
    ls,
    read_file,
    standard_tools,
    update_todo_status,
    write_file,
    write_todos,
)

# Local helper to load the examples planner tool via path-based import to avoid
# collisions with any site-packages module named "examples".
def _load_planner_tool():
    try:
        import importlib.util as _il
        from pathlib import Path as _Path

        mod_path = _Path(__file__).resolve().parents[1] / "inspect" / "exploration" / "planner_tool.py"
        if not mod_path.exists():  # optional component
            return None
        spec = _il.spec_from_file_location("_examples_planner_tool", str(mod_path))
        if spec is None or spec.loader is None:
            return None
        mod = _il.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[arg-type]
        return getattr(mod, "planner_tool")()
    except Exception:
        return None


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
            # Load planner API by path to avoid site-packages name conflicts
            import importlib.util as _il
            base = Path(__file__).resolve().parents[1] / "inspect" / "exploration"
            spec_p = _il.spec_from_file_location("_examples_planner", str(base / "planner.py"))
            spec_c = _il.spec_from_file_location("_examples_cfg_loader", str(base / "config_loader.py"))
            if spec_p and spec_p.loader and spec_c and spec_c.loader:
                mod_p = _il.module_from_spec(spec_p); spec_p.loader.exec_module(mod_p)  # type: ignore[arg-type]
                mod_c = _il.module_from_spec(spec_c); spec_c.loader.exec_module(mod_c)  # type: ignore[arg-type]
                cfg = mod_c.load_exploration_config(None)
                items = mod_p.plan(prompt, cfg)
                # Build JSON like planner_tool (filter out seeds depth<1)
                q = []
                for it in items:
                    d = int(getattr(it, "depth", 0))
                    if d < 1:
                        continue
                    q.append({
                        "query": getattr(it, "query", ""),
                        "depth": d,
                        "tags": list(getattr(it, "tags", []) or []),
                    })
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
        # Build base tools and sub-agents inline (same as the local runner)
        builtins = [write_todos(), update_todo_status(), write_file(), read_file(), ls(), edit_file()]
        base_tools = builtins + standard_tools()

        sub_research_prompt = (
            "You are a dedicated researcher. Your job is to conduct research based on the user's question.\n\n"
            "Conduct thorough research and then reply with a detailed answer."
        )
        sub_critique_prompt = (
            "You are a dedicated editor tasked to critique a report.\n\n"
            "The report is in `final_report.md`; the question is in `question.txt`.\n"
            "Respond with a detailed critique and concrete improvements."
        )

        sub_configs = [
            {
                "name": "research-agent",
                "description": (
                    "Used to research more in-depth questions. Only give this researcher one topic at a time."
                ),
                "prompt": sub_research_prompt,
                "tools": ["web_search", "read_file", "write_file", "ls"],
                "mode": "handoff",
            },
            {
                "name": "critique-agent",
                "description": "Used to critique the final report.",
                "prompt": sub_critique_prompt,
                "tools": ["web_search", "read_file", "write_file", "ls"],
                "mode": "handoff",
            },
        ]

        subagent_tools = build_subagents(configs=sub_configs, base_tools=base_tools)

        # Expose planner tool to the supervisor (not to sub-agents)
        _planner = _load_planner_tool()
        extra_tools = [_planner] if _planner is not None else []

        agent = build_supervisor(
            prompt="You are a helpful researcher.",
            tools=subagent_tools + extra_tools,
            attempts=attempts,
            model=model_id,
        )

    return Task(
        dataset=[Sample(input=prompt)],
        solver=agent,
    )
