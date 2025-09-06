"""
Simple Architecture — Runnable Demo

This minimal, self-contained script wires together the public Inspect Agents
APIs to demonstrate the "Simple Architecture" in code:

- Supervisor built via `build_supervisor(...)` with built‑in Todo/FS tools and
  optional standard tools (think/web_search/bash/python, gated by env).
- One sub‑agent (handoff): "researcher" with a small message budget.
- Approvals enabled via environment preset (INSPECT_APPROVAL_PRESET).
- Run with `run_agent(...)` and persist a redacted transcript to `.inspect/logs`.

Usage
  uv run python examples/demos/simple_architecture.py "What is x?"

Env examples
  NO_NETWORK=1 \
  INSPECT_APPROVAL_PRESET=dev \
  uv run python examples/demos/simple_architecture.py "What is x?"

Notes
- No CLI dependencies; uses only library entry points.
- Optional standard tools (web_search, exec, browser) are controlled by env.
  See docs/reference/environment.md for flags.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any


def _ensure_repo_paths() -> None:
    """Best-effort: add local repo paths for examples run without install.

    Insert `<repo>/src` and `<repo>/external/inspect_ai/src` to `sys.path` if
    they exist. This keeps the demo runnable via `uv run python ...` without
    requiring `uv sync` or `pip install -e .`.
    """
    here = Path(__file__).resolve()
    repo = here.parents[2]  # examples/demos/ -> repo root
    candidates = [repo / "src", repo / "external" / "inspect_ai" / "src"]
    for p in candidates:
        if p.exists():
            sp = str(p)
            if sp not in sys.path:
                sys.path.insert(0, sp)


_ensure_repo_paths()


async def _build_demo_agent() -> Any:
    # Local imports after sys.path setup
    from inspect_agents.agents import build_subagents, build_supervisor
    from inspect_agents.tools import (
        edit_file,
        ls,
        read_file,
        standard_tools,
        update_todo_status,
        write_file,
        write_todos,
    )

    # Optional per-subagent limits (Prefer the Inspect util when available; fall back to shim)
    try:
        from inspect_ai.util._limit import message_limit  # type: ignore
    except Exception:
        from inspect_agents.config import message_limit  # type: ignore

    # Compose a base tool universe for sub‑agents (Todo/FS + optional standard tools)
    base_universe = [
        write_todos(),
        update_todo_status(),
        write_file(),
        read_file(),
        ls(),
        edit_file(),
        *standard_tools(),  # gated by env flags & provider creds
    ]

    # One sub-agent: researcher
    sub_cfgs = [
        {
            "name": "researcher",
            "description": "Finds information and drafts concise answers.",
            "prompt": (
                "You are a focused researcher.\n"
                "- Gather relevant facts.\n"
                "- Use web_search if enabled; prefer citing sources.\n"
                "- Keep answers short and to the point.\n"
            ),
            "mode": "handoff",
            "limits": [message_limit(8)],
        }
    ]

    sub_tools = build_subagents(configs=sub_cfgs, base_tools=base_universe)

    supervisor_prompt = (
        "You are the supervisor.\n"
        "Route to the 'researcher' when needed, then call submit with a final answer."
    )
    # Offline-friendly default model: if no ambient model is configured via
    # INSPECT_EVAL_MODEL, use a tiny agent that immediately submits a stub.
    from inspect_ai.agent._agent import agent as as_agent
    from inspect_ai.model._chat_message import ChatMessageAssistant
    from inspect_ai.model._model_output import ModelOutput
    from inspect_ai.tool._tool_call import ToolCall

    @as_agent
    def demo_model():
        async def execute(state, tools):
            # Emit a submit tool call with a small placeholder answer.
            submit_call = ToolCall(
                id="call_1",
                function="submit",
                arguments={"answer": "Demo complete (no model configured)."},
            )
            msg = ChatMessageAssistant(content="Submitting demo answer.", tool_calls=[submit_call], source="generate")
            state.messages.append(msg)
            state.output = ModelOutput.from_message(msg)
            return state

        return execute

    ambient_model = os.getenv("INSPECT_EVAL_MODEL")
    model_arg: Any = None if ambient_model else demo_model()
    return build_supervisor(prompt=supervisor_prompt, tools=sub_tools, model=model_arg)


async def main() -> None:
    # Args
    ap = argparse.ArgumentParser(description="Simple Architecture runnable demo")
    ap.add_argument("query", help="User query to run", nargs="?", default="start")
    args = ap.parse_args()

    # Build agent graph
    agent = await _build_demo_agent()

    # Run with approvals from env (INSPECT_APPROVAL_PRESET) if set.
    from inspect_agents.run import run_agent
    result = await run_agent(agent, args.query, return_limit_error=True)

    # Unpack when limits produce a (state, err) tuple; otherwise just state
    if isinstance(result, tuple):
        state, err = result
    else:
        state, err = result, None

    # Persist transcript and print the path
    from inspect_agents.logging import write_transcript

    log_path = write_transcript(os.getenv("INSPECT_LOG_DIR"))
    print(log_path)

    # Optional: print a minimal completion to provide immediate feedback
    try:
        output = getattr(state, "output", None)
        completion = getattr(output, "completion", None)
        if isinstance(completion, str) and completion.strip():
            print("---\n" + completion)
    except Exception:
        pass

    # If a limit error occurred, surface a one-line note (exit code remains 0)
    if err is not None:
        try:
            name = type(err).__name__
            print(f"[limit]: {name}")
        except Exception:
            print("[limit]: error")


if __name__ == "__main__":
    asyncio.run(main())
