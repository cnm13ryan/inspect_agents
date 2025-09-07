#!/usr/bin/env python3
"""
Exploration Runner (Supervisor → Planner → Research → Critique)

Purpose
- Orchestrates a simple, auditable deep‑research flow using Inspect‑AI agents
  and repo tools: planner_tool → research‑agent → critique‑agent.

Outputs (virtual Files store)
- plan.json       — planner output (JSON)
- question.txt    — original user question
- final_report.md — synthesized report (post‑critique)

Usage
- uv run python -m examples.inspect.exploration.runner \
    --attempts 3 \
    --config examples/configs/research/exploration.yaml \
    "Investigate <topic>"

Notes
- Approvals: uses approval_preset("ci") — permissive; no exclusivity/kill‑switch.
- Web search optional: works with or without INSPECT_ENABLE_WEB_SEARCH=1. When
  disabled, the research agent still produces a report based on available
  context; planner artifacts are always produced.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

from inspect_agents.agents import build_subagents, build_supervisor
from inspect_agents.approval import approval_preset
from inspect_agents.model import resolve_model
from inspect_agents.run import run_agent
from inspect_agents.tools import (
    edit_file,
    ls,
    read_file,
    standard_tools,
    update_todo_status,
    write_file,
    write_todos,
)

# Local tool: exploration planner exposed as an Inspect tool
# Import planner_tool with a robust fallback so this module works when loaded
# via package import (python -m) or via path-based import in the Inspect task.
try:
    from .planner_tool import planner_tool  # type: ignore
except Exception:  # pragma: no cover - fallback for file-based import
    import importlib.util as _il
    from pathlib import Path as _Path

    _mod_path = _Path(__file__).with_name("planner_tool.py")
    _spec = _il.spec_from_file_location("_examples_planner_tool", str(_mod_path))
    if _spec is None or _spec.loader is None:
        raise ImportError(f"Unable to load planner_tool from {_mod_path}")
    _mod = _il.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)  # type: ignore[arg-type]
    planner_tool = getattr(_mod, "planner_tool")


def _load_exploration_config(path: str | None) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Load optional exploration YAML.

    Returns a tuple: (policy, scoring, supervisor) where each element is a
    plain dict or None if missing/invalid.
    """
    if not path:
        return None, None, None
    p = Path(path)
    if not p.exists():
        return None, None, None
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return None, None, None

        # Support both nested sections and flat policy-only docs
        policy = data.get("policy") if isinstance(data.get("policy"), dict) else None
        scoring = data.get("scoring") if isinstance(data.get("scoring"), dict) else None
        supervisor = data.get("supervisor") if isinstance(data.get("supervisor"), dict) else None

        if policy is None:
            # If the file is a flat dict of planner fields, treat it as policy
            # (legacy behavior)
            non_nested = {k: v for k, v in data.items() if k not in {"scoring", "supervisor"}}
            policy = non_nested or None

        return (dict(policy) if policy else None,
                dict(scoring) if scoring else None,
                dict(supervisor) if supervisor else None)
    except Exception:
        return None, None, None


def _load_planner_config(path: str | None) -> dict[str, Any] | None:
    """Legacy helper retained for compatibility (returns policy only)."""
    pol, _, _ = _load_exploration_config(path)
    return pol


def _supervisor_prompt(planner_cfg: dict[str, Any] | None, *, override_text: str | None = None) -> str:
    cfg_text = (
        "\nPlanner config (JSON):\n" + json.dumps(planner_cfg, ensure_ascii=False)
        if planner_cfg
        else ""
    )
    preface = (override_text + "\n\n") if override_text else ""
    return (
        preface
        + "You are the orchestrator of a small research workflow.\n\n"
        "Goal\n"
        "- Generate a plan via planner_tool, write it to plan.json.\n"
        "- Write the user's question verbatim to question.txt.\n"
        "- Handoff to research-agent to execute the plan and write final_report.md.\n"
        "- After that, handoff to critique-agent for an editorial pass; then return.\n\n"
        "Instructions\n"
        "1) Call planner_tool with prompt=<user input>. If a planner config is provided below, pass it as the 'config' argument.\n"
        "   - If planner_tool errors or returns invalid output, immediately write a minimal fallback plan to plan.json:\n"
        "     {\"queries\": [{\"query\": <user input>, \"depth\": 1, \"tags\": [\"seed\"]}], \"breadth\": 1, \"depth\": 1}.\n"
        "2) Save the plan JSON to plan.json using write_file (even for fallback).\n"
        "3) Save the input question to question.txt using write_file.\n"
        "4) Handoff to research-agent (transfer_to_research-agent).\n"
        "5) After it finishes, handoff to critique-agent (transfer_to_critique-agent).\n"
        "Important: Use one tool call at a time; avoid parallel tool invocations.\n"
        + cfg_text
    )

def _research_prompt(override_text: str | None = None) -> str:
    if override_text:
        return override_text
    return (
        "You are the research-agent.\n\n"
        "- Read plan.json and question.txt.\n"
        "- Execute the planned queries serially (top items first). Prefer web_search when available;\n"
        "  if unavailable, synthesize from context and still write a report.\n"
        "- If plan.json is missing or has no queries, synthesize a minimal plan with the user's question as the only query and proceed.\n"
        "- Capture findings with concise evidence and include inline citations like [1], [2], etc.,\n"
        "  followed by a References section mapping numbers to sources (title + URL when web_search is used).\n"
        "- Write a single markdown report to final_report.md using write_file.\n"
        "- Keep outputs grounded, structured, and complete.\n"
    )


def _critique_prompt(override_text: str | None = None) -> str:
    if override_text:
        return override_text
    return (
        "You are the critique-agent.\n\n"
        "- Read final_report.md and question.txt.\n"
        "- Improve structure, clarity, completeness, and citation hygiene.\n"
        "- Make edits directly and overwrite final_report.md using write_file.\n"
        "- Keep the original research question and scope unchanged.\n"
    )


def build_runner_agent(
    *,
    planner_cfg: dict[str, Any] | None,
    attempts: int,
    model: Any | None,
    supervisor_prompts: Optional[Dict[str, str]] = None,
    scoring_cfg: Optional[Dict[str, Any]] = None,
):
    """Construct supervisor + sub-agents and return an Inspect agent.

    - Adds `planner_tool()` to the supervisor tool list.
    - Sub-agents are exposed via handoff tools: transfer_to_research-agent, transfer_to_critique-agent.
    """

    # Built-ins + standard tools
    builtins = [write_todos(), update_todo_status(), write_file(), read_file(), ls(), edit_file()]
    base_tools = builtins + standard_tools()

    # Sub-agents (handoffs)
    sub_configs = [
        {
            "name": "research-agent",
            "description": (
                "Used to research more in-depth questions. Only give this researcher one topic at a time."
            ),
            "prompt": _research_prompt((supervisor_prompts or {}).get("research")),
            "tools": ["web_search", "read_file", "write_file", "ls"],
            "mode": "handoff",
        },
        {
            "name": "critique-agent",
            "description": "Used to critique the final report.",
            "prompt": _critique_prompt((supervisor_prompts or {}).get("critique")),
            "tools": ["read_file", "write_file", "ls"],
            "mode": "handoff",
        },
    ]

    subagent_tools = build_subagents(configs=sub_configs, base_tools=base_tools)

    # Supervisor with planner tool + subagent handoffs
    sup = build_supervisor(
        prompt=_supervisor_prompt(planner_cfg, override_text=(supervisor_prompts or {}).get("supervisor")),
        tools=[planner_tool()] + subagent_tools,
        attempts=attempts,
        model=model,
    )
    return sup


async def _amain(args: argparse.Namespace) -> None:
    # Resolve model once for the run
    model_id = resolve_model()

    # Load optional exploration YAML (policy/scoring/supervisor)
    planner_cfg, scoring_cfg, supervisor_cfg = _load_exploration_config(args.config)

    # Supervisor attempts: YAML override takes precedence over CLI flag if present
    yaml_attempts = None
    if supervisor_cfg and isinstance(supervisor_cfg.get("attempts"), int):
        yaml_attempts = int(supervisor_cfg["attempts"])
    effective_attempts = yaml_attempts if yaml_attempts is not None else args.attempts

    prompts = None
    if supervisor_cfg and isinstance(supervisor_cfg.get("prompts"), dict):
        # Coerce keys to str->str
        raw = supervisor_cfg["prompts"]
        prompts = {str(k): str(v) for k, v in raw.items()}

    agent = build_runner_agent(
        planner_cfg=planner_cfg,
        attempts=effective_attempts,
        model=model_id,
        supervisor_prompts=prompts,
        scoring_cfg=scoring_cfg,
    )

    # Approvals: permissive CI preset (no exclusivity/kill-switch by default)
    approvals = approval_preset("ci")

    # Run the agent with the provided prompt
    await run_agent(agent, args.prompt, approval=approvals)


def main() -> None:
    parser = argparse.ArgumentParser(description="Exploration runner: planner → research → critique")
    parser.add_argument(
        "prompt",
        type=str,
        help="Research question, e.g., 'Investigate <topic>'",
    )
    parser.add_argument(
        "--config",
        dest="config",
        default=None,
        help="Optional planner config YAML (e.g., examples/configs/research/exploration.yaml)",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=3,
        help="Supervisor attempts (submit-terminated ReAct loop)",
    )

    args = parser.parse_args()
    asyncio.run(_amain(args))


if __name__ == "__main__":
    main()
