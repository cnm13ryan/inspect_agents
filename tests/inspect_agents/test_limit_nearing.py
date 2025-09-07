import asyncio
import json
from typing import Any

import pytest


def _install_stub_run(monkeypatch, sleep_s: float, return_tuple: bool = True):
    """Install a stub for `inspect_ai.agent._run.run` that sleeps then returns.

    When `return_tuple` is True, mimics Inspect behavior under limits by returning
    `(state, err)` where `err` is None. Otherwise returns `state` only.
    """

    # Import the real module chain so we can safely patch the symbol
    import inspect_ai.agent._run as real_run_module  # type: ignore

    class _State:
        pass

    async def run(_agent: Any, _input: Any, **_kwargs: Any):
        await asyncio.sleep(sleep_s)
        st = _State()
        return (st, None) if return_tuple else st

    # Patch the attribute; pytest will restore after the test
    monkeypatch.setattr(real_run_module, "run", run, raising=False)


def _tool_logs(caplog):
    caplog.set_level("INFO", logger="inspect_agents.tools")
    return caplog


def _extract_limit_nearing_events(records):
    events = []
    for rec in records:
        msg = getattr(rec, "message", "")
        if not isinstance(msg, str):
            continue
        if not msg.startswith("tool_event "):
            continue
        try:
            payload = json.loads(msg.split(" ", 1)[1])
        except Exception:
            continue
        if payload.get("tool") == "observability":
            continue
        if (
            payload.get("tool") == "limits"
            and payload.get("phase") == "info"
            and payload.get("event") == "limit_nearing"
        ):
            events.append(payload)
    return events


@pytest.mark.asyncio
async def test_limit_nearing_emits_when_past_threshold(monkeypatch, caplog):
    # Arrange: stub runner to last past near threshold (sleep 0.15s)
    _install_stub_run(monkeypatch, sleep_s=0.15, return_tuple=True)

    # Set threshold 0.5; with 0.2s limit => near at 0.1s
    monkeypatch.setenv("INSPECT_LIMIT_NEARING_THRESHOLD", "0.5")

    # Build a real Inspect time_limit object
    from inspect_ai.util._limit import time_limit  # type: ignore

    limits = [time_limit(0.2)]

    # Capture logs
    _tool_logs(caplog)

    # Act
    from inspect_agents.run import run_agent

    _ = await run_agent(agent=object(), input="hi", limits=limits)

    # Assert: one info event for limit_nearing
    events = _extract_limit_nearing_events(caplog.records)
    assert len(events) == 1, f"expected one near-limit event, got {events}"
    ev = events[0]
    assert ev.get("kind") == "time"
    assert abs(float(ev.get("threshold", 0.0)) - 0.2) < 1e-6
    assert abs(float(ev.get("used", 0.0)) - 0.1) < 1e-6


@pytest.mark.asyncio
async def test_limit_nearing_not_emitted_when_completes_early(monkeypatch, caplog):
    # Arrange: completes before near threshold (sleep 0.05s; near=0.15s)
    _install_stub_run(monkeypatch, sleep_s=0.05, return_tuple=True)

    # Threshold 0.75; with 0.2s limit => near at 0.15s
    monkeypatch.setenv("INSPECT_LIMIT_NEARING_THRESHOLD", "0.75")

    from inspect_ai.util._limit import time_limit  # type: ignore

    limits = [time_limit(0.2)]

    _tool_logs(caplog)

    from inspect_agents.run import run_agent

    _ = await run_agent(agent=object(), input="hi", limits=limits)

    # Assert: no near-limit event since run finished before threshold and timer cancelled
    events = _extract_limit_nearing_events(caplog.records)
    assert events == []
