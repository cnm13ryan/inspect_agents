#!/usr/bin/env python3
"""
Exploration Runner (legacy shim)

Deprecated path: examples.inspect.exploration.runner

This module remains as a thin shim for backward compatibility. It emits
DeprecationWarning and delegates execution to the consolidated runner at
examples/runners/exploration_runner.py. Internal prompt helpers are kept
so that existing tests that reference them (e.g., _supervisor_prompt)
continue to function during the deprecation window.
"""

from __future__ import annotations

import argparse
import json
import warnings
from typing import Any

from examples.runners import exploration_runner as _new_runner

# Deprecated shim utilities
_MSG = "examples.inspect.exploration.runner is deprecated; use examples/runners/exploration_runner.py"


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
    warnings.warn(_MSG, DeprecationWarning, stacklevel=2)
    return _new_runner.build_runner_agent(
        planner_cfg=planner_cfg,
        attempts=attempts,
        model=model,
        supervisor_prompts=supervisor_prompts,
        scoring_cfg=scoring_cfg,
    )


async def _amain(args: argparse.Namespace) -> None:
    warnings.warn(_MSG, DeprecationWarning, stacklevel=2)
    await _new_runner._amain(args)


def main() -> None:
    warnings.warn(_MSG, DeprecationWarning, stacklevel=2)
    _new_runner.main()


if __name__ == "__main__":
    main()
