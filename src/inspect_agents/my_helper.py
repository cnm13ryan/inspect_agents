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
    # Return a simple iterative agent.
    return build_iterative_agent(
        prompt=prompt or DEFAULT_PROMPT,
        code_only=True,
        # Keep loops tight for demos; customize as needed
        real_time_limit_sec=30,
        max_steps=10,
        **kwargs,
    )
