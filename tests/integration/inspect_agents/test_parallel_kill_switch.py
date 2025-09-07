# test(approvals): add integration tests for parallel kill-switch and handoff interplay

import asyncio
import importlib
import logging

import pytest

from tests.fixtures.helpers import (
    build_apply_shim,
    ensure_vendor_on_path,
    parse_tool_events,
)

pytestmark = pytest.mark.kill_switch


def test_kill_switch_logs_skips_and_rejects_subsequent_calls(monkeypatch, caplog):
    ensure_vendor_on_path()
    build_apply_shim(monkeypatch)

    # Enable kill-switch via either canonical env var
    monkeypatch.setenv("INSPECT_TOOL_PARALLELISM_DISABLE", "1")
    monkeypatch.delenv("INSPECT_DISABLE_TOOL_PARALLEL", raising=False)

    from inspect_ai.log._transcript import ToolEvent, Transcript, init_transcript, transcript
    from inspect_ai.model._chat_message import ChatMessageAssistant
    from inspect_ai.tool._tool_call import ToolCall

    approval = importlib.import_module("inspect_agents.approval")
    from inspect_ai.approval._apply import apply_tool_approval, init_tool_approval

    # Activate only the kill-switch policy
    init_tool_approval(approval.parallel_kill_switch_policy())
    init_transcript(Transcript())

    # Two non-handoff calls in one assistant turn
    msg = ChatMessageAssistant(
        content="",
        tool_calls=[
            ToolCall(id="1", function="echo_a", arguments={}),
            ToolCall(id="2", function="echo_b", arguments={}),
        ],
    )
    history = [msg]

    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    ok1, a1 = asyncio.run(apply_tool_approval(msg.text, msg.tool_calls[0], None, history))
    ok2, a2 = asyncio.run(apply_tool_approval(msg.text, msg.tool_calls[1], None, history))

    assert ok1 and getattr(a1, "decision", None) == "approve"
    assert not ok2 and getattr(a2, "decision", None) == "reject"
    assert "only first" in (getattr(a2, "explanation", "") or "").lower()

    # Transcript reflects the skip event for the second call
    tev = transcript().find_last_event(ToolEvent)
    assert tev is not None and getattr(tev, "id", None) == "2"
    assert getattr(tev, "function", None) == "echo_b"
    assert getattr(tev, "error", None) is not None
    assert getattr(tev.error, "message", "").lower().startswith("parallel disabled")
    assert isinstance(tev.metadata, dict)
    assert tev.metadata.get("source") == "policy/parallel_kill_switch"
    assert tev.metadata.get("first_allowed_id") == "1"
    assert tev.metadata.get("skipped_function") == "echo_b"

    # Repo-local logger emits a skipped event for kill switch
    events = parse_tool_events(caplog)
    skipped = [e for e in events if e.get("tool") == "parallel_kill_switch" and e.get("phase") == "skipped"]
    # Exactly one subsequent call in this test, so exactly one skipped event
    assert len(skipped) == 1, "Expected a single parallel_kill_switch skipped event"

    # Cleanup env
    monkeypatch.delenv("INSPECT_TOOL_PARALLELISM_DISABLE", raising=False)


def test_kill_switch_escalates_when_handoff_present(monkeypatch, caplog):
    ensure_vendor_on_path()
    build_apply_shim(monkeypatch)

    # Enable kill-switch; presence of handoff should escalate to exclusivity
    monkeypatch.setenv("INSPECT_TOOL_PARALLELISM_DISABLE", "1")

    from inspect_ai.log._transcript import Transcript, init_transcript
    from inspect_ai.model._chat_message import ChatMessageAssistant
    from inspect_ai.tool._tool_call import ToolCall

    approval = importlib.import_module("inspect_agents.approval")
    from inspect_ai.approval._apply import apply_tool_approval, init_tool_approval

    # Compose both policies with canonical ordering
    init_tool_approval(approval.approval_chain())
    init_transcript(Transcript())

    # One handoff + one non-handoff in the same assistant message
    handoff = ToolCall(id="h1", function="transfer_to_delegate", arguments={})
    other = ToolCall(id="2", function="echo_b", arguments={})
    msg = ChatMessageAssistant(content="", tool_calls=[handoff, other])
    history = [msg]

    caplog.set_level(logging.INFO, logger="inspect_agents.tools")

    ok_h, ah = asyncio.run(apply_tool_approval(msg.text, handoff, None, history))
    ok_o, ao = asyncio.run(apply_tool_approval(msg.text, other, None, history))

    # First handoff approved by exclusivity policy
    assert ok_h and getattr(ah, "decision", None) == "approve"

    # Non-handoff rejected by exclusivity (not by kill-switch)
    assert not ok_o and getattr(ao, "decision", None) == "reject"
    assert "handoff exclusivity" in (getattr(ao, "explanation", "") or "").lower()

    # Logs should show handoff_exclusive skipped, and not parallel_kill_switch
    events = parse_tool_events(caplog)
    assert any(e.get("tool") == "handoff_exclusive" and e.get("phase") == "skipped" for e in events)
    assert not any(e.get("tool") == "parallel_kill_switch" for e in events), (
        "Kill-switch should escalate; no skip logged"
    )

    # Cleanup env
    monkeypatch.delenv("INSPECT_TOOL_PARALLELISM_DISABLE", raising=False)
