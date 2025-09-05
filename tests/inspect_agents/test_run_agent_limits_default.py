# test(run): limits default is immutable across calls

import asyncio
import sys
import types


def _install_inspect_stub(calls: list[dict]) -> None:
    """Install a minimal stub for `inspect_ai.agent._run.run`.

    The stub records the `limits` argument and mutates it to simulate a
    framework that appends to the provided list, which would reveal leakage
    if a mutable default list were shared across calls.
    """

    async def run(agent, input, limits=None, **_):  # type: ignore[no-untyped-def]
        calls.append({
            "id": id(limits),
            "list": list(limits) if limits is not None else None,
        })
        if limits is not None:
            # Simulate framework mutation that would persist if caller reused
            # a shared default list between invocations.
            limits.append("SENTINEL")
            return ("STATE", None)
        return "STATE"

    # Create package/module hierarchy: inspect_ai -> agent -> _run
    pkg = types.ModuleType("inspect_ai")
    mod_agent = types.ModuleType("inspect_ai.agent")
    mod_run = types.ModuleType("inspect_ai.agent._run")
    mod_run.run = run  # type: ignore[attr-defined]

    sys.modules["inspect_ai"] = pkg
    sys.modules["inspect_ai.agent"] = mod_agent
    sys.modules["inspect_ai.agent._run"] = mod_run


def _uninstall_inspect_stub() -> None:
    for name in ("inspect_ai.agent._run", "inspect_ai.agent", "inspect_ai"):
        sys.modules.pop(name, None)


def test_run_agent_limits_default_isolated():
    calls: list[dict] = []
    _install_inspect_stub(calls)
    try:
        from inspect_agents.run import run_agent

        async def main() -> None:
            # Call twice without providing `limits`
            state1 = await run_agent(agent="A", input="x")
            state2 = await run_agent(agent="B", input="y")

            # Both calls unwrap to the state-only value
            assert state1 == "STATE"
            assert state2 == "STATE"

        asyncio.run(main())

        # Verify two calls recorded
        assert len(calls) == 2

        # Each call should receive a fresh, empty list for `limits`
        # (no accumulation from the first call's mutation)
        assert calls[0]["list"] == []
        assert calls[1]["list"] == []
    finally:
        _uninstall_inspect_stub()
