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
async def test_env_profile_sets_sandbox_and_logs(monkeypatch, caplog):
    from inspect_agents.run import run_agent

    _install_engine_stub(monkeypatch)

    # Arrange: set profile and start with strict toggles to ensure they change
    monkeypatch.setenv("INSPECT_PROFILE", "T1.H1.N2")
    monkeypatch.setenv("INSPECT_ENABLE_WEB_SEARCH", "0")
    monkeypatch.setenv("INSPECT_ENABLE_EXEC", "1")
    monkeypatch.setenv("INSPECT_ENABLE_WEB_BROWSER", "1")

    caplog.set_level("INFO", logger="inspect_agents.tools")

    # Act
    out = await run_agent(agent=object(), input="x")

    # Assert engine executed
    assert out == "STATE"

    # Sandbox env convenience exported for CLI code paths
    import os

    assert os.getenv("INSPECT_EVAL_SANDBOX") == "docker"

    # Web-only toggles enforced
    assert os.getenv("INSPECT_ENABLE_WEB_SEARCH") == "1"
    assert os.getenv("INSPECT_ENABLE_EXEC") == "0"
    assert os.getenv("INSPECT_ENABLE_WEB_BROWSER") == "0"

    # Log contains a profile tool_event
    logs = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "tool_event" in logs and '"tool": "profile"' in logs
