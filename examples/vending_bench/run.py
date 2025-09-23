"""Evaluation harness for the Vending-Bench supervisor + sub-agent stack."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

# Inspect limits
from inspect_ai.util._limit import message_limit, time_limit, token_limit

from inspect_agents.agents import build_subagents, build_supervisor
from inspect_agents.model import resolve_model
from inspect_agents.run import run_agent

from .. import _utils
from .config import EnvConfig
from .env import VendingEnv
from .memory import (
    _CHECKPOINT_DIR_ENV,
    _RESUME_ENV,
    _RUN_ID_ENV,
    MemoryStore,
    memory_tools,
)
from .metrics import collect_episode_metrics
from .prompts import PHYSICAL_AGENT_PROMPT, SUPERVISOR_PROMPT
from .runtime import clear_runtime_context, set_runtime_context
from .tools import physical_agent_tools, supervisor_tools


def _tool_names(tools: list[Any]) -> list[str]:
    names: list[str] = []
    try:
        from inspect_ai.tool._tool_def import ToolDef  # type: ignore

        for tool in tools:
            try:
                names.append(ToolDef(tool).name)
            except Exception:
                names.append(getattr(tool, "name", getattr(tool, "__name__", "unknown_tool")))
    except Exception:
        for tool in tools:
            names.append(getattr(tool, "name", getattr(tool, "__name__", "unknown_tool")))
    return names


def build_supervisor_agent(model: str, *, include_defaults: bool = False) -> Any:
    """Construct the supervisor with required tools and sub-agent handoff."""

    physical_tools = physical_agent_tools()
    subagent_configs = [
        {
            "name": "vending",
            "description": "Physical operations specialist for restocking, pricing, and cash collection.",
            "prompt": PHYSICAL_AGENT_PROMPT,
            "tools": _tool_names(physical_tools),
            "limits": [message_limit(16), token_limit(6000)],
        }
    ]
    subagents = build_subagents(
        configs=subagent_configs,
        base_tools=physical_tools,
        default_model=model,
    )

    supervisor_toolset = supervisor_tools() + memory_tools() + subagents

    return build_supervisor(
        prompt=SUPERVISOR_PROMPT,
        tools=supervisor_toolset,
        include_defaults=include_defaults,
        attempts=1,
        model=model,
        truncation="auto",
    )


def build_limits(config: EnvConfig) -> list[Any]:
    """Create Inspect runtime limits for the harness run."""

    return [
        time_limit(600),  # 10 minutes wall clock per episode
        message_limit(config.max_turns),
        token_limit(200_000),
    ]


async def _run_agent(agent: Any, user_input: str, limits: list[Any]) -> Any:
    return await run_agent(agent=agent, input=user_input, limits=limits, raise_on_limit=True)


def _summarise_state(state: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    output = getattr(state, "output", None)
    completion = getattr(output, "completion", None)
    if completion:
        summary["completion"] = completion
    messages = getattr(state, "messages", None)
    if messages is not None:
        try:
            summary["message_count"] = len(messages)
        except Exception:
            pass
    return summary


def _initialise_memory_store(*, run_id: str | None, checkpoint_dir: Path | None, resume: bool) -> MemoryStore:
    if run_id and checkpoint_dir:
        directory = checkpoint_dir.expanduser()
        store = MemoryStore.load_checkpoint(directory=directory, run_id=run_id) if resume else None
        if store is None:
            store = MemoryStore()
        store.configure_checkpoint(directory=directory, run_id=run_id, auto_persist=True)
        return store
    return MemoryStore()


def run_episode(
    seed: int,
    model: str,
    *,
    include_defaults: bool = False,
    run_id: str | None = None,
    checkpoint_dir: Path | None = None,
    resume: bool = False,
) -> dict[str, Any]:
    config = EnvConfig(seed=seed)
    env = VendingEnv(config)
    memory = _initialise_memory_store(run_id=run_id, checkpoint_dir=checkpoint_dir, resume=resume)

    set_runtime_context(env=env, memory=memory)
    try:
        agent = build_supervisor_agent(model, include_defaults=include_defaults)
        user_input = "Manage the vending machine business for the day."
        state = asyncio.run(_run_agent(agent, user_input, build_limits(config)))
    finally:
        clear_runtime_context()

    env.state.telemetry["seed"] = seed

    metrics = collect_episode_metrics(env.state)
    metrics["conversation"] = _summarise_state(state)
    metrics["config"] = {
        "seed": seed,
        "model": model,
        "include_defaults": include_defaults,
    }
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Vending-Bench harness")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic seed for the simulator")
    _utils.add_common_model_flags(parser)
    _utils.add_common_tool_flags(parser)
    parser.add_argument("--output", type=Path, help="Optional path to write JSON metrics")
    parser.add_argument(
        "--include-default-tools", action="store_true", help="Inject inspect_agents default tool preset"
    )
    parser.add_argument("--run-id", type=str, help="Identifier used for memory checkpointing")
    parser.add_argument(
        "--resume-run", action="store_true", help="Resume the memory checkpoint for the provided run id"
    )
    parser.add_argument(
        "--memory-checkpoint-dir",
        type=Path,
        default=Path(".inspect/vending_checkpoints"),
        help="Directory used to store per-run memory checkpoints",
    )
    args = parser.parse_args()

    _utils.apply_tool_env_from_args(args)
    _utils.ensure_repo_src_on_path()
    _utils.load_env_files(Path(__file__).parent, include_template=True)

    run_id = args.run_id
    checkpoint_dir = args.memory_checkpoint_dir if run_id else None
    resume_run = bool(args.resume_run and run_id)

    if run_id:
        os.environ[_RUN_ID_ENV] = run_id
        os.environ[_CHECKPOINT_DIR_ENV] = str(args.memory_checkpoint_dir)
        if resume_run:
            os.environ[_RESUME_ENV] = "1"
        else:
            os.environ.pop(_RESUME_ENV, None)
    else:
        os.environ.pop(_RUN_ID_ENV, None)
        os.environ.pop(_CHECKPOINT_DIR_ENV, None)
        os.environ.pop(_RESUME_ENV, None)

    model_id = resolve_model(provider=args.provider, model=args.model)
    metrics = run_episode(
        seed=args.seed,
        model=model_id,
        include_defaults=args.include_default_tools,
        run_id=run_id,
        checkpoint_dir=checkpoint_dir,
        resume=resume_run,
    )

    output = json.dumps(metrics, indent=2)
    if args.output:
        args.output.write_text(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
