#!/usr/bin/env python3
"""
Inspect‑AI runner for the research example (no external agent frameworks).

What it does
- Loads .env files (repo root, this folder, or --env-file) without overriding
  existing env vars.
- Resolves a local‑first model via inspect_agents and runs a minimal supervisor
  once with the provided prompt.
- Prints the final completion and writes a transcript JSONL path.

Usage
  uv run python examples/runners/research_runner.py "What is Inspect‑AI?"
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import importlib.util as _il
from importlib.util import module_from_spec, spec_from_file_location
from types import ModuleType
from typing import Optional

# Robustly import local examples/_utils.py even if a site-packages "examples" exists
_UTILS_PATH = Path(__file__).resolve().parents[1] / "_utils.py"
_spec = _il.spec_from_file_location("_examples_utils_local", str(_UTILS_PATH))
if _spec is None or _spec.loader is None:  # pragma: no cover - defensive
    raise ImportError(f"Unable to load utils from {_UTILS_PATH}")
_utils = _il.module_from_spec(_spec)
_spec.loader.exec_module(_utils)

# Prefer local repo sources over any installed wheel
_utils.ensure_repo_src_on_path()


def _load_planner_tool() -> Optional[object]:
    """Load the examples planner tool as a Tool object, if present.

    Uses path-based import to avoid collisions with any site-packages module
    named "examples".
    """
    try:
        mod_path = Path(__file__).resolve().parents[1] / "inspect" / "exploration" / "planner_tool.py"
        if not mod_path.exists():
            return None
        spec = spec_from_file_location("_examples_planner_tool", str(mod_path))
        if spec is None or spec.loader is None:
            return None
        mod: ModuleType = module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[arg-type]
        return getattr(mod, "planner_tool")()
    except Exception:
        return None


async def _main() -> int:
    from inspect_agents.agents import build_subagents, build_supervisor
    from inspect_agents.approval import approval_preset, handoff_exclusive_policy
    from inspect_agents.config import load_and_build
    from inspect_agents.logging import write_transcript
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

    parser = argparse.ArgumentParser(
        description="Run the Inspect‑AI research supervisor.",
        epilog=(
            "Quarantine: control handoff input filtering via INSPECT_QUARANTINE_MODE "
            "(strict|scoped|off) and INSPECT_QUARANTINE_INHERIT=0/1."
        ),
    )
    parser.add_argument("prompt", nargs="*", help="User prompt text")
    parser.add_argument(
        "--provider",
        default=os.getenv("DEEPAGENTS_MODEL_PROVIDER", "ollama"),
        help="Model provider (ollama, lm-studio, openai, ...)",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("INSPECT_EVAL_MODEL"),
        help="Explicit model name (optional; provider prefix allowed)",
    )
    parser.add_argument(
        "--enable-web-search",
        action="store_true",
        help="Enable Inspect standard web_search tool",
    )
    parser.add_argument(
        "--approval",
        choices=["dev", "ci", "prod"],
        help="Apply an approvals preset (dev|ci|prod)",
    )
    parser.add_argument(
        "--config",
        help="Load composition from YAML (inspect_agents.config)",
    )
    args = parser.parse_args()

    user_input = " ".join(args.prompt).strip() or os.getenv(
        "PROMPT", "Write a short overview of Inspect‑AI"
    )
    if args.enable_web_search:
        os.environ["INSPECT_ENABLE_WEB_SEARCH"] = "1"

    # Local‑first: let resolver choose provider/model (defaults to Ollama if unset)
    model_id = resolve_model(provider=args.provider, model=args.model)
    # Test hook: short-circuit and echo resolved model for subprocess tests
    if os.getenv("DEEPAGENTS_TEST_ECHO_MODEL") == "1":
        print(model_id)
        return 0

    # Debug: show effective tool-output cap once
    try:
        _utils.print_effective_tool_output_limit()
    except Exception:
        pass

    # If a YAML config is provided, build from config; else use the inline composition
    yaml_agent = None
    yaml_approvals = []
    yaml_limits = []
    if args.config:
        yaml_agent, _, yaml_approvals, yaml_limits = load_and_build(args.config, model=model_id)
        agent = yaml_agent
    else:
        # Build base tools for sub-agents (same composition as library built-ins)
        builtins = [write_todos(), update_todo_status(), write_file(), read_file(), ls(), edit_file()]
        base_tools = builtins + standard_tools()

        # Sub-agent prompts (lightweight researcher and critique roles)
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

        subagent_tools = build_subagents(configs=sub_configs, base_tools=base_tools, default_model=model_id)

        # Expose planner tool to the supervisor (not to sub-agents)
        planner = _load_planner_tool()
        extra_tools = [planner] if planner is not None else []

        agent = build_supervisor(
            prompt="You are a helpful researcher.",
            tools=subagent_tools + extra_tools,
            attempts=1,
            model=model_id,
        )
    # Approval policies (optional): apply preset and handoff exclusivity in dev/prod/ci
    policies = list(yaml_approvals or []) or None
    if args.approval:
        extra = list(approval_preset(args.approval))
        if args.approval in {"dev", "prod", "ci"}:
            extra.extend(handoff_exclusive_policy())
        policies = (policies or []) + extra
    result = await run_agent(agent, user_input, approval=policies, limits=yaml_limits)

    # Print the final assistant completion and transcript log path
    completion = getattr(result.output, "completion", None)
    print(completion or "[No completion]")
    print("Transcript:", write_transcript())
    return 0


def main() -> None:
    # Optional lightweight pre-parse of --env-file to point at a specific env
    try:
        mini = argparse.ArgumentParser(add_help=False)
        mini.add_argument("--env-file")
        known, _ = mini.parse_known_args()
        if known.env_file:
            os.environ["INSPECT_ENV_FILE"] = known.env_file
    except Exception:
        pass

    _utils.load_env_files(Path(__file__).parent, include_template=True)
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
