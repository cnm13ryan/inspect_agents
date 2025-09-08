#!/usr/bin/env python3
"""Monolithic CLI for examples (python -m examples ...).

Subcommands (thin wrappers around existing runners/builders):
- supervisor: minimal supervisor
- iterative: iterative agent loop
- research: research composition (optionally via YAML config)
- exploration: planner → research → critique runner (YAML-aware)
- debug model-explain: delegate to debug/model_explain.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path


def _ensure_repo_src_on_path() -> None:
    here = Path(__file__).resolve()
    repo_root = here.parents[1]
    src = repo_root / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _load_utils():
    # Import local examples._utils without colliding with site-packages
    import importlib.util as _il

    util_path = Path(__file__).with_name("_utils.py")
    spec = _il.spec_from_file_location("_examples_utils_local", str(util_path))
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Unable to load examples/_utils.py from {util_path}")
    mod = _il.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod


async def _run_supervisor(args, utils) -> int:  # type: ignore[no-untyped-def]
    from inspect_agents.agents import build_supervisor
    from inspect_agents.logging import write_transcript
    from inspect_agents.model import resolve_model
    from inspect_agents.run import run_agent

    utils.apply_tool_env_from_args(args)
    model_id = resolve_model(provider=args.provider, model=args.model)
    agent = build_supervisor(prompt="You are helpful.", tools=[], attempts=1, model=model_id)
    user_input = " ".join(args.prompt).strip() or os.getenv("PROMPT", "Write a short overview of LangGraph")
    result = await run_agent(agent, user_input)
    print(getattr(result.output, "completion", None) or "[No completion]")
    try:
        print("Transcript:", write_transcript())
    except Exception:
        pass
    return 0


async def _run_iterative(args, utils) -> int:  # type: ignore[no-untyped-def]
    from inspect_agents.agents import build_iterative_agent
    from inspect_agents.model import resolve_model
    from inspect_agents.run import run_agent

    utils.apply_tool_env_from_args(args)
    model_id = resolve_model(provider=args.provider, model=args.model)
    if os.getenv("DEEPAGENTS_TEST_ECHO_MODEL") == "1":
        print(model_id)
        return 0
    agent = build_iterative_agent(
        prompt=(
            "You are an iterative coding agent. Work in small, verifiable steps. "
            "Use tools when needed and keep the repo tidy."
        ),
        model=model_id,
        real_time_limit_sec=int(args.time_limit),
        max_steps=int(args.max_steps),
    )
    user_input = " ".join(args.prompt).strip() or os.getenv(
        "PROMPT", "List repository files and propose a small refactor plan."
    )
    state = await run_agent(agent, user_input)
    print(getattr(state.output, "completion", None) or "[No assistant text]")
    return 0


async def _run_research(args, utils) -> int:  # type: ignore[no-untyped-def]
    from examples.lib.builders import build_research_supervisor
    from inspect_agents.config import load_and_build
    from inspect_agents.model import resolve_model
    from inspect_agents.run import run_agent

    utils.apply_tool_env_from_args(args)
    model_id = resolve_model(provider=args.provider, model=args.model)
    if args.config:
        agent, *_ = load_and_build(args.config, model=model_id)
    else:
        agent = build_research_supervisor(model=model_id, attempts=1, include_planner=True)
    user_input = " ".join(args.prompt).strip() or os.getenv("PROMPT", "Write a short overview of Inspect‑AI")
    result = await run_agent(agent, user_input)
    print(getattr(result.output, "completion", None) or "[No completion]")
    return 0


async def _run_exploration(args, utils) -> int:  # type: ignore[no-untyped-def]
    from examples.lib.builders import build_exploration_supervisor
    from examples.lib.exploration.config_loader import load_exploration_sections
    from inspect_agents.approval import approval_preset
    from inspect_agents.model import resolve_model
    from inspect_agents.run import run_agent

    utils.apply_tool_env_from_args(args)
    model_id = resolve_model(provider=args.provider, model=args.model)
    planner_cfg, _scoring_cfg, supervisor_cfg = load_exploration_sections(args.config)

    yaml_attempts = None
    if supervisor_cfg and isinstance(supervisor_cfg.get("attempts"), int):
        yaml_attempts = int(supervisor_cfg["attempts"])
    attempts = yaml_attempts if yaml_attempts is not None else int(args.attempts)

    prompts = None
    if supervisor_cfg and isinstance(supervisor_cfg.get("prompts"), dict):
        raw = supervisor_cfg["prompts"]
        prompts = {str(k): str(v) for k, v in raw.items()}

    agent = build_exploration_supervisor(
        model=model_id, attempts=attempts, planner_cfg=planner_cfg, prompts_override=prompts
    )
    approvals = approval_preset("ci")
    result = await run_agent(agent, args.prompt, approval=approvals)
    print(getattr(result.output, "completion", None) or "[No completion]")
    return 0


def _run_debug_model_explain(argv: list[str], utils) -> int:  # type: ignore[no-untyped-def]
    # Delegate to examples/debug/model_explain.py main()
    mod = utils.import_by_path("examples.debug.model_explain", Path(__file__).parent / "debug" / "model_explain.py")
    return int(mod.main(argv))  # type: ignore[attr-defined]


def main(argv: list[str] | None = None) -> int:
    _ensure_repo_src_on_path()
    utils = _load_utils()
    utils.load_env_files(Path(__file__).parent, include_template=True)

    p = argparse.ArgumentParser(prog="python -m examples", description="Examples monolithic CLI")
    p.add_argument("--env-file", help=".env file to load (applies before subcommand)")
    subs = p.add_subparsers(dest="cmd", required=True)

    # supervisor
    ps = subs.add_parser("supervisor", help="Minimal supervisor")
    ps.add_argument("prompt", nargs="*", help="User prompt text")
    utils.add_common_model_flags(ps)
    utils.add_common_tool_flags(ps)
    ps.set_defaults(_fn=lambda a: _run_supervisor(a, utils))

    # iterative
    pi = subs.add_parser("iterative", help="Iterative agent loop (no submit)")
    pi.add_argument("prompt", nargs="*", help="User prompt text (default from $PROMPT)")
    pi.add_argument("--time-limit", type=int, default=600, help="Real-time limit in seconds (default 600)")
    pi.add_argument("--max-steps", type=int, default=40, help="Max loop steps (default 40)")
    utils.add_common_model_flags(pi)
    utils.add_common_tool_flags(pi)
    pi.set_defaults(_fn=lambda a: _run_iterative(a, utils))

    # research
    pr = subs.add_parser("research", help="Research composition (optional YAML)")
    pr.add_argument("prompt", nargs="*", help="User prompt text")
    utils.add_common_model_flags(pr)
    utils.add_common_tool_flags(pr)
    pr.add_argument("--approval", choices=["dev", "ci", "prod"], help="Apply approvals preset (dev|ci|prod)")
    pr.add_argument("--config", help="Load composition from YAML (inspect_agents.config)")
    pr.set_defaults(_fn=lambda a: _run_research(a, utils))

    # exploration
    px = subs.add_parser("exploration", help="Planner → research → critique (YAML-aware)")
    px.add_argument("prompt", type=str, help="Research question, e.g., 'Investigate <topic>'")
    px.add_argument(
        "--config", default=None, help="Optional planner config YAML (examples/configs/research/exploration.yaml)"
    )
    px.add_argument("--attempts", type=int, default=3, help="Supervisor attempts (submit-terminated ReAct loop)")
    utils.add_common_model_flags(px)
    utils.add_common_tool_flags(px)
    px.set_defaults(_fn=lambda a: _run_exploration(a, utils))

    # debug group
    pd = subs.add_parser("debug", help="Diagnostics and utilities")
    dsubs = pd.add_subparsers(dest="dbg", required=True)
    pme = dsubs.add_parser("model-explain", help="Explain provider/model resolution")
    pme.add_argument("-p", "--provider")
    pme.add_argument("-m", "--model")
    pme.add_argument("-r", "--role")
    pme.add_argument("--json", action="store_true")
    pme.set_defaults(_fn=lambda a: _run_debug_model_explain(sys.argv[sys.argv.index("model-explain") + 1 :], utils))

    args = p.parse_args(argv)
    if args.env_file:
        os.environ["INSPECT_ENV_FILE"] = args.env_file
        # Re-load after setting explicit file
        utils.load_env_files(Path(__file__).parent, include_template=True)

    # One-time debug print of tool-output cap
    try:
        utils.print_effective_tool_output_limit()
    except Exception:
        pass

    fn = getattr(args, "_fn", None)
    if fn is None:
        p.print_help()
        return 1
    rv = fn(args)
    if asyncio.iscoroutine(rv):  # type: ignore[arg-type]
        return asyncio.run(rv)  # type: ignore[arg-type]
    return int(rv)


if __name__ == "__main__":
    raise SystemExit(main())
