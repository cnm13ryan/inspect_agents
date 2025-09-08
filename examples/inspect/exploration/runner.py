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
from typing import Any

from examples.lib.builders import build_exploration_supervisor
from examples.lib.exploration.config_loader import (
    load_exploration_sections,
)
from inspect_agents.approval import approval_preset
from inspect_agents.model import resolve_model
from inspect_agents.run import run_agent

# Note: YAML loading is centralized in examples.lib.exploration.config_loader.


def _supervisor_prompt(planner_cfg: dict[str, Any] | None, *, override_text: str | None = None) -> str:
    cfg_text = "\nPlanner config (JSON):\n" + json.dumps(planner_cfg, ensure_ascii=False) if planner_cfg else ""
    preface = (override_text + "\n\n") if override_text else ""
    return (
        preface + "You are the orchestrator of a small research workflow.\n\n"
        "Goal\n"
        "- Generate a plan via planner_tool, write it to plan.json.\n"
        "- Write the user's question verbatim to question.txt.\n"
        "- Handoff to research-agent to execute the plan and write final_report.md.\n"
        "- After that, handoff to critique-agent for an editorial pass; then return.\n\n"
        "Instructions\n"
        "1) Call planner_tool with prompt=<user input>. If a planner config is provided below, pass it as the 'config' argument.\n"
        "   - If planner_tool errors or returns invalid output, immediately write a minimal fallback plan to plan.json:\n"
        '     {"queries": [{"query": <user input>, "depth": 1, "tags": ["seed"]}], "breadth": 1, "depth": 1}.\n'
        "2) Save the plan JSON to plan.json using write_file (even for fallback).\n"
        "3) Save the input question to question.txt using write_file.\n"
        "4) Handoff to research-agent (transfer_to_research-agent).\n"
        "5) After it finishes, handoff to critique-agent (transfer_to_critique-agent).\n"
        "Important: Use one tool call at a time; avoid parallel tool invocations.\n" + cfg_text
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
    supervisor_prompts: dict[str, str] | None = None,
    scoring_cfg: dict[str, Any] | None = None,
):
    """Construct supervisor via shared builder and return an Inspect agent.

    Retains the historical function name for test compatibility while
    delegating to `examples.lib.builders.build_exploration_supervisor`.
    """
    return build_exploration_supervisor(
        model=model,
        attempts=attempts,
        planner_cfg=planner_cfg,
        prompts_override=supervisor_prompts,
    )


async def _amain(args: argparse.Namespace) -> None:
    # Resolve model once for the run
    model_id = resolve_model()

    # Load optional exploration YAML (policy/scoring/supervisor)
    planner_cfg, scoring_cfg, supervisor_cfg = load_exploration_sections(args.config)

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
