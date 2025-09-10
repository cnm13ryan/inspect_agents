# Minimal agent factory for inspect_agents.my_helper.
#
# Edit the default prompt and parameters as desired. By default this
# uses code-only tools (no exec/search/browser) so it runs safely in
# offline tests. To enable more tools, configure environment flags per
# `inspect_agents.tools.standard_tools()`.

from __future__ import annotations

from typing import Any

from inspect_agents.agents import build_iterative_agent

DEFAULT_PROMPT = (
    "You are a helpful, concise assistant. Prefer file read/edit tools; avoid executing code or using the web."
)


def build_agent(*, prompt: str | None = None, **kwargs: Any) -> Any:
    """Return a tiny agent suitable for quick demos/tests.

    Tries to build the real iterative agent. If upstream `inspect_ai` pieces
    are unavailable (e.g., in highly sandboxed test environments), falls back
    to a minimal dummy object that works with tests that stub the runner.
    """
    try:
        return build_iterative_agent(
            prompt=prompt or DEFAULT_PROMPT,
            code_only=True,
            # Keep loops tight for demos; customize as needed
            real_time_limit_sec=30,
            max_steps=10,
            **kwargs,
        )
    except Exception:
        # Fallback: return a simple sentinel object; tests that patch
        # `inspect_ai.agent._run.run` do not depend on the agent's internals.
        _p = prompt or DEFAULT_PROMPT

        class _DummyAgent:
            prompt = _p

            def __repr__(self) -> str:  # pragma: no cover - trivial
                return "<inspect_agents.my_helper.DummyAgent>"

        return _DummyAgent()
