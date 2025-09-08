#!/usr/bin/env python3
"""
Run the Inspect Agents Iterative Agent (no submit): small, time/step‑bounded steps.

Examples
- Minimal:  uv run python examples/runners/iterative_runner.py "List repo files and summarize"
- With exec: INSPECT_ENABLE_EXEC=1 \
             uv run python examples/runners/iterative_runner.py --time-limit 300 --max-steps 20 \
               "Create docs/OUTLINE.md and add 3 sections"

Environment
- Model routing prefers local by default (Ollama). To change provider/model, use
  CLI flags `--provider/--model` or set env as described in
  docs/reference/environment.md.
- Optional tools via env flags (see docs/tools/*):
  - INSPECT_ENABLE_EXEC=1          # enable bash() and python() tools
  - INSPECT_ENABLE_WEB_SEARCH=1    # enable web_search (requires API keys)
  - INSPECT_ENABLE_WEB_BROWSER=1   # enable browser tools
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util as _il
import os
from pathlib import Path
from types import ModuleType as _ModuleType  # noqa: F401

# Robustly import local examples/_utils.py even if a site-packages "examples" exists.
# Prefer normal import first; fall back to path-based import when necessary.
try:
    from examples import _utils as _utils  # type: ignore
except Exception:  # pragma: no cover - defensive path-based fallback
    _UTILS_PATH = Path(__file__).resolve().parents[1] / "_utils.py"
    _spec = _il.spec_from_file_location("_examples_utils_local", str(_UTILS_PATH))
    if _spec is None or _spec.loader is None:
        raise ImportError(f"Unable to load utils from {_UTILS_PATH}")
    _utils = _il.module_from_spec(_spec)
    _spec.loader.exec_module(_utils)

# Prefer local repo sources over any installed wheel
_utils.ensure_repo_src_on_path()


async def _main() -> int:
    # Local imports to ensure src/ precedence without violating E402
    from inspect_agents.agents import build_iterative_agent
    from inspect_agents.model import resolve_model
    from inspect_agents.run import run_agent

    parser = argparse.ArgumentParser(description="Run the Iterative Agent (no submit).")
    parser.add_argument("prompt", nargs="*", help="User prompt text (default from $PROMPT)")
    parser.add_argument("--time-limit", type=int, default=600, help="Real-time limit in seconds (default 600)")
    parser.add_argument("--max-steps", type=int, default=40, help="Max loop steps (default 40)")
    # Common flags across runners
    _utils.add_common_model_flags(parser)
    _utils.add_common_tool_flags(parser)
    args = parser.parse_args()

    user_input = " ".join(args.prompt).strip() or os.getenv(
        "PROMPT", "List repository files and propose a small refactor plan."
    )

    # Apply tool flags uniformly
    _utils.apply_tool_env_from_args(args)

    # Resolve model (prefers local Ollama by default; CLI/env may override)
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

    agent = build_iterative_agent(
        prompt=(
            "You are an iterative coding agent. Work in small, verifiable steps. "
            "Use tools when needed and keep the repo tidy."
        ),
        model=model_id,
        real_time_limit_sec=args.time_limit,
        max_steps=args.max_steps,
    )

    state = await run_agent(agent, user_input)

    # Best-effort: print completion or last assistant text
    text: str | None = getattr(state.output, "completion", None)
    if not text:
        try:
            text = state.output.choices[-1].message.text  # type: ignore[attr-defined]
        except Exception:
            text = None
    print(text or "[No assistant text]")
    return 0


def main() -> None:
    _utils.load_env_files(Path(__file__).parent, include_template=True)
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
