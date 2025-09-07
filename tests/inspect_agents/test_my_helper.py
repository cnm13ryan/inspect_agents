import asyncio
from typing import Any

import pytest


def _install_stub_run(monkeypatch, sleep_s: float = 0.01, return_tuple: bool = True):
    """Install a stub for `inspect_ai.agent._run.run` to avoid provider calls."""
    import inspect_ai.agent._run as real_run_module  # type: ignore

    class _State:
        pass

    async def run(_agent: Any, _input: Any, **_kwargs: Any):
        await asyncio.sleep(sleep_s)
        st = _State()
        return (st, None) if return_tuple else st

    monkeypatch.setattr(real_run_module, "run", run, raising=False)


@pytest.mark.asyncio
async def test_my_helper_smoke(monkeypatch):
    monkeypatch.setenv("NO_NETWORK", "1")

    # Provide a tiny runner time limit; our stub returns quickly.
    from inspect_ai.util._limit import time_limit  # type: ignore

    from inspect_agents.run import run_agent

    _install_stub_run(monkeypatch)

    from inspect_agents.my_helper import build_agent

    agent = build_agent()
    state = await run_agent(agent=agent, input="ping", limits=[time_limit(0.01)])
    assert state is not None
