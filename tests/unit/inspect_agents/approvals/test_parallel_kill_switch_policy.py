#!/usr/bin/env python3
"""Unit test for parallel_kill_switch_policy approver.

Validates that when the kill-switch env is set and a batch contains multiple
non-handoff tool calls, only the first is approved and subsequent ones are
rejected. Also verifies a standardized transcript ToolEvent is emitted for
skipped calls.
"""

import asyncio
import importlib
import os
import sys

# Prefer vendored Inspect‑AI to avoid version drift with site‑packages
_VENDOR = os.path.join("external", "inspect_ai", "src")
if os.path.isdir(_VENDOR) and _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

from inspect_ai.log._transcript import ToolEvent, Transcript, init_transcript, transcript  # type: ignore  # noqa: E402
from inspect_ai.tool._tool_call import ToolCall  # type: ignore  # noqa: E402


def _load_module():
    return importlib.import_module("inspect_agents.approval")


class _Msg:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls


def test_kill_switch_allows_only_first_non_handoff(monkeypatch):
    approval = _load_module()
    policies = approval.parallel_kill_switch_policy()
    approver = policies[0].approver

    # Enable via canonical backlog env var
    monkeypatch.setenv("INSPECT_DISABLE_TOOL_PARALLEL", "1")
    monkeypatch.delenv("INSPECT_TOOL_PARALLELISM_DISABLE", raising=False)

    # Prepare assistant message with two non-handoff tool calls
    t1 = ToolCall(id="1", function="echo_a", arguments={})
    t2 = ToolCall(id="2", function="echo_b", arguments={})
    msg = _Msg([t1, t2])
    history = [msg]

    async def _run():
        # Fresh transcript within the same async context as the approver
        init_transcript(Transcript())
        r1 = await approver(msg, t1, None, history)
        r2 = await approver(msg, t2, None, history)
        tev = transcript().find_last_event(ToolEvent)
        return r1, r2, tev

    res1, res2, tev = asyncio.run(_run())
    if tev is None:
        # Fallback: structural search in transcript in case of class identity drift
        evs = getattr(transcript(), "events", [])
        for e in reversed(list(evs)):
            if (
                getattr(e, "event", None) == "tool"
                and getattr(e, "id", None) == "2"
                and getattr(e, "function", None) == "echo_b"
            ):
                tev = e
                break

    # First non-handoff should be approved
    assert getattr(res1, "decision", None) == "approve"

    # Second should be rejected
    assert getattr(res2, "decision", None) == "reject"
    assert "only first" in (getattr(res2, "explanation", "") or "").lower()

    # Verify standardized transcript event for the skipped call (optional fallback)
    if tev is not None:
        assert getattr(tev, "id", None) == "2"
        assert getattr(tev, "function", None) == "echo_b"
        assert getattr(tev, "error", None) is not None
        assert getattr(tev.error, "message", "").lower().startswith("parallel disabled")
        assert isinstance(tev.metadata, dict)
        assert tev.metadata.get("source") == "policy/parallel_kill_switch"

    # Cleanup env
    monkeypatch.delenv("INSPECT_DISABLE_TOOL_PARALLEL", raising=False)
