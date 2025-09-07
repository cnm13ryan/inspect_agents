# test(run): env-selectable approval preset path

import sys
import types

import pytest


def _install_engine_stub(monkeypatch):
    """Install a minimal stub for `inspect_ai.agent._run.run` that returns a state.

    Keeps tests fast and isolated from the real Inspect engine.
    """

    async def run(agent, input, limits=None, **_):  # type: ignore[no-untyped-def]
        # Ensure `run_agent` normalized limits to a list
        assert isinstance(limits, list)
        return "STATE"

    mod_run = types.ModuleType("inspect_ai.agent._run")
    mod_run.run = run  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "inspect_ai.agent._run", mod_run)


@pytest.mark.asyncio
async def test_env_preset_applies_when_no_explicit_approval(monkeypatch):
    # Arrange: env preset set and approval activation monkeypatched to capture calls
    from inspect_agents import approval as approval_mod

    called: list[list[object]] = []

    def fake_activate(policies):  # type: ignore[no-untyped-def]
        called.append(list(policies or []))

    def fake_preset(name: str):  # return deterministic sentinel
        assert name == "dev"
        return ["PRESET_SENTINEL"]

    monkeypatch.setenv("INSPECT_APPROVAL_PRESET", "dev")
    monkeypatch.setattr(approval_mod, "activate_approval_policies", fake_activate)
    monkeypatch.setattr(approval_mod, "approval_preset", fake_preset)
    _install_engine_stub(monkeypatch)

    from inspect_agents.run import run_agent

    # Act
    out = await run_agent(agent=object(), input="x")

    # Assert: engine ran and preset was activated exactly once
    assert out == "STATE"
    assert len(called) == 1
    assert called[0] == ["PRESET_SENTINEL"]


@pytest.mark.asyncio
async def test_env_preset_ignored_when_explicit_approval_provided(monkeypatch):
    # Arrange: env preset set, but explicit approval passed to run_agent
    from inspect_agents import approval as approval_mod

    called: list[list[object]] = []

    def fake_activate(policies):  # type: ignore[no-untyped-def]
        called.append(list(policies or []))

    monkeypatch.setenv("INSPECT_APPROVAL_PRESET", "dev")
    monkeypatch.setattr(approval_mod, "activate_approval_policies", fake_activate)
    _install_engine_stub(monkeypatch)

    from inspect_agents.run import run_agent

    # Act: provide explicit approvals to the runner
    out = await run_agent(agent=object(), input="y", approval=["EXPLICIT"])

    # Assert: engine ran and env preset was NOT activated
    assert out == "STATE"
    assert called == []
