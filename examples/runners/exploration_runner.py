#!/usr/bin/env python3
"""
Exploration Runner (Supervisor → Planner → Research → Critique)

Context
- Consolidated runner located under examples/runners for consistency with
  other runnable scripts. Maintains the same behavior as the legacy
  examples/inspect/exploration/runner.py entrypoint.

Behavior
- Loads optional YAML policy (planner/scoring/supervisor) via
  examples.lib.exploration.config_loader.
- Composes the exploration supervisor using build_exploration_supervisor.
- Runs with approval_preset("ci").

Artifacts (virtual Files store)
- plan.json       — planner output (JSON)
- question.txt    — original user question
- final_report.md — synthesized report (post‑critique)

Usage
- uv run python examples/runners/exploration_runner.py \
    --attempts 3 \
    --config examples/configs/research/exploration.yaml \
    "Investigate <topic>"
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from examples.lib.builders import build_exploration_supervisor
from examples.lib.exploration.config_loader import load_exploration_sections
from inspect_agents.approval import approval_preset
from inspect_agents.model import resolve_model
from inspect_agents.run import run_agent


def build_runner_agent(
    *,
    planner_cfg: dict[str, Any] | None,
    attempts: int,
    model: Any | None,
    supervisor_prompts: dict[str, str] | None = None,
    scoring_cfg: dict[str, Any] | None = None,
):
    """Construct and return the exploration supervisor agent.

    Delegates to examples.lib.builders.build_exploration_supervisor to avoid
    duplication and to keep parity with other entrypoints.
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
