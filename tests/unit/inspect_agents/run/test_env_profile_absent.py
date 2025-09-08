import os
import sys
import types

import pytest


def _install_engine_stub(monkeypatch):
    async def run(agent, input, limits=None, **_):  # type: ignore[no-untyped-def]
        assert isinstance(limits, list)
        return "STATE"

    mod_run = types.ModuleType("inspect_ai.agent._run")
    mod_run.run = run  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "inspect_ai.agent._run", mod_run)


@pytest.mark.asyncio
async def test_no_profile_env_does_not_modify_toggles_or_log(monkeypatch, caplog):
    from inspect_agents.run import run_agent

    _install_engine_stub(monkeypatch)

    # Ensure no profile is present
    monkeypatch.delenv("INSPECT_PROFILE", raising=False)

    # Seed toggles with sentinel values
    monkeypatch.setenv("INSPECT_ENABLE_WEB_SEARCH", "0")
    monkeypatch.setenv("INSPECT_ENABLE_EXEC", "0")
    monkeypatch.setenv("INSPECT_ENABLE_WEB_BROWSER", "0")

    caplog.set_level("INFO", logger="inspect_agents.tools")

    out = await run_agent(agent=object(), input="x")
    assert out == "STATE"

    # No sandbox hint exported
    assert os.getenv("INSPECT_EVAL_SANDBOX") is None

    # Toggles unchanged
    assert os.getenv("INSPECT_ENABLE_WEB_SEARCH") == "0"
    assert os.getenv("INSPECT_ENABLE_EXEC") == "0"
    assert os.getenv("INSPECT_ENABLE_WEB_BROWSER") == "0"

    # No profile tool_event in logs
    logs = "\n".join(rec.getMessage() for rec in caplog.records)
    assert '"tool": "profile"' not in logs
