import json
import logging
import sys
import types

import pytest


class FakeLimitError(Exception):
    def __init__(self, kind: str = "time_limit", threshold: float = 1.0, used: float = 2.0):
        super().__init__(f"{kind} exceeded: used={used}, threshold={threshold}")
        self.kind = kind
        self.threshold = threshold
        self.used = used


def _collect_limits_events(records):
    events = []
    for rec in records:
        msg = rec.getMessage()
        if isinstance(msg, str) and msg.startswith("tool_event "):
            try:
                payload = json.loads(msg[len("tool_event ") :])
            except Exception:
                continue
            if payload.get("tool") == "limits" and payload.get("phase") == "error":
                events.append(payload)
    return events


@pytest.mark.asyncio
async def test_runner_emits_single_limits_event_on_error(caplog, monkeypatch):
    # Capture logs from our package loggers
    caplog.set_level(logging.INFO, logger="inspect_agents")
    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    # Stub Inspect's agent.run to return a (state, err) tuple with a limit error
    mod = types.ModuleType("inspect_ai.agent._run")

    async def fake_run(agent, input, limits=None):  # type: ignore[no-untyped-def]
        return ({"ok": True}, FakeLimitError(kind="time_limit", threshold=0.01, used=0.02))

    mod.run = fake_run  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "inspect_ai.agent._run", mod)

    # Import target after stubbing to ensure our fake is used
    from inspect_agents.run import run_agent

    before = len(caplog.records)
    # Call with default semantics (no raise, no tuple return)
    state = await run_agent(agent=object(), input="hi", limits=["dummy-limit"])
    assert isinstance(state, dict) and state.get("ok") is True

    # Verify exactly one structured "limits" event was logged
    events = _collect_limits_events(caplog.records[before:])
    assert len(events) == 1, f"expected 1 limits event, got {len(events)}: {events}"
    evt = events[0]
    assert evt.get("tool") == "limits"
    assert evt.get("phase") == "error"
    assert evt.get("scope") == "runner"
    assert evt.get("error_type") == "FakeLimitError"
    # Optional enrichment fields when available on the error
    assert evt.get("kind") == "time_limit"
    assert evt.get("threshold") == 0.01
    assert evt.get("used") == 0.02

    # Call a second time; ensure one limits event per call (no duplicates)
    before2 = len(caplog.records)
    state2 = await run_agent(agent=object(), input="hi2", limits=["dummy-limit"])
    assert isinstance(state2, dict) and state2.get("ok") is True

    events2 = _collect_limits_events(caplog.records[before2:])
    assert len(events2) == 1, f"expected 1 limits event on second call, got {len(events2)}: {events2}"
    evt2 = events2[0]
    assert evt2.get("tool") == "limits" and evt2.get("phase") == "error"
    assert evt2.get("error_type") == "FakeLimitError"
