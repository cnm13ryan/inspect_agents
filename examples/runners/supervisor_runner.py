#!/usr/bin/env python3
"""
Run the Inspect‑AI path (inspect_agents) from the repo.

Features
- Loads .env from repo root and this folder (if present)
- Resolves model via inspect_agents (defaults to LM‑Studio or env)
- Runs a minimal supervisor and prints the final completion
- Writes a transcript JSONL and prints its path

Usage
  uv run python examples/runners/supervisor_runner.py "Write a short overview of LangGraph"

Environment
- DEEPAGENTS_MODEL_PROVIDER=ollama|lm-studio|openai|...
- LM_STUDIO_BASE_URL, LM_STUDIO_MODEL_NAME, LM_STUDIO_API_KEY (for LM‑Studio)
- OLLAMA_MODEL_NAME, OLLAMA_BASE_URL/OLLAMA_HOST (for Ollama)
- PROMPT (optional default prompt)
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util as _il
import os
from pathlib import Path

# Robustly import local examples/_utils.py even if a site-packages "examples" exists
_UTILS_PATH = Path(__file__).resolve().parents[1] / "_utils.py"
_spec = _il.spec_from_file_location("_examples_utils_local", str(_UTILS_PATH))
if _spec is None or _spec.loader is None:  # pragma: no cover - defensive
    raise ImportError(f"Unable to load utils from {_UTILS_PATH}")
_utils = _il.module_from_spec(_spec)
_spec.loader.exec_module(_utils)

# Prefer local repo sources over any installed wheel
_utils.ensure_repo_src_on_path()


async def _main() -> int:
    from inspect_agents.agents import build_supervisor
    from inspect_agents.logging import write_transcript
    from inspect_agents.model import resolve_model
    from inspect_agents.run import run_agent

    parser = argparse.ArgumentParser(description="Run the Inspect Agents supervisor.")
    parser.add_argument("prompt", nargs="*", help="User prompt text")
    # Common flags across runners
    _utils.add_common_model_flags(parser)
    _utils.add_common_tool_flags(parser)
    args = parser.parse_args()

    user_input = " ".join(args.prompt).strip() or os.getenv("PROMPT", "Write a short overview of LangGraph")

    # Reflect flags into env uniformly before building agent
    _utils.apply_tool_env_from_args(args)

    # Debug: show effective tool-output cap once
    try:
        _utils.print_effective_tool_output_limit()
    except Exception:
        pass

    model_id = resolve_model(provider=args.provider, model=args.model)
    agent = build_supervisor(prompt="You are helpful.", tools=[], attempts=1, model=model_id)
    result = await run_agent(agent, user_input)

    # Print the final assistant completion and transcript log path
    completion = getattr(result.output, "completion", None)
    print(completion or "[No completion]")
    print("Transcript:", write_transcript())
    return 0


def main() -> None:
    # Allow a lightweight pre-parse of --env-file to point at a specific env
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
