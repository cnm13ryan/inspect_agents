import logging
from typing import Any

import pytest

from inspect_agents.iterative import (
    _append_overflow_hint,
    _prune_with_debug,
    _remaining_timeout,
    _should_emit_progress,
)


def test_should_emit_progress_basic():
    assert _should_emit_progress(10, 5) is True
    assert _should_emit_progress(11, 5) is False


def test_should_emit_progress_edge_cases():
    assert _should_emit_progress(1, None) is False
    assert _should_emit_progress(5, 0) is False
    # Malformed input should not raise and should return False
    assert _should_emit_progress(5, "abc") is False  # type: ignore[arg-type]


def test_remaining_timeout_none_limit():
    # No overall limit -> None per-call timeout
    assert (
        _remaining_timeout(start=0.0, limit_sec=None, total_retry_time=0.0, productive_time_enabled=False, now=10.0)
        is None
    )


def test_remaining_timeout_clamps_and_productive_time():
    # With productive time disabled: wall=110-100=10, limit=20 -> remaining=10
    assert (
        _remaining_timeout(start=100.0, limit_sec=20, total_retry_time=0.0, productive_time_enabled=False, now=110.0)
        == 10
    )
    # With productive time enabled: elapsed=(110-100)-7=3, remaining=17
    assert (
        _remaining_timeout(start=100.0, limit_sec=20, total_retry_time=7.0, productive_time_enabled=True, now=110.0)
        == 17
    )
    # Exhausted/negative budget clamps to at least 1
    assert (
        _remaining_timeout(start=100.0, limit_sec=5, total_retry_time=0.0, productive_time_enabled=False, now=106.0)
        == 1
    )


def test_append_overflow_hint_appends_exact_string():
    from inspect_ai.model._chat_message import ChatMessageUser

    msgs: list[Any] = [ChatMessageUser(content="hello")]
    _append_overflow_hint(msgs)
    assert isinstance(msgs[-1], ChatMessageUser)
    assert getattr(msgs[-1], "content", None) == "Context too long; please summarize recent steps and continue."


def test_prune_with_debug_threshold_logs_and_keeps_tail(caplog: pytest.LogCaptureFixture):
    from inspect_ai.model._chat_message import ChatMessageUser

    # Build 5 simple user messages
    msgs: list[Any] = [ChatMessageUser(content=f"m{i}") for i in range(5)]
    caplog.set_level(logging.INFO, logger="inspect_agents.iterative")

    pruned = _prune_with_debug(
        msgs,
        keep_last=2,
        token_cap=None,  # skip token-aware truncation for determinism
        last_k=10,
        debug=True,
        reason="threshold",
        threshold=4,
    )
    # Contract: first user is preserved + last keep_last tail => 1 + 2 = 3
    assert len(pruned) == 3
    # Composition: first preserved user, then last two tail entries
    contents = [getattr(m, "content", None) for m in pruned]
    assert contents == ["m0", "m3", "m4"]
    # Expect exact threshold log format (post reflects first user + tail)
    expect = "Prune: reason=threshold pre=5 post=3 keep_last=2 threshold=4"
    assert any(expect in rec.getMessage() for rec in caplog.records)


def test_prune_with_debug_overflow_logs(caplog: pytest.LogCaptureFixture):
    from inspect_ai.model._chat_message import ChatMessageUser

    msgs: list[Any] = [ChatMessageUser(content=f"m{i}") for i in range(5)]
    caplog.set_level(logging.INFO, logger="inspect_agents.iterative")

    pruned = _prune_with_debug(
        msgs,
        keep_last=2,
        token_cap=None,
        last_k=10,
        debug=True,
        reason="overflow",
    )
    # Contract: first user is preserved + last keep_last tail => 1 + 2 = 3
    assert len(pruned) == 3
    contents = [getattr(m, "content", None) for m in pruned]
    assert contents == ["m0", "m3", "m4"]
    expect = "Prune: reason=overflow pre=5 post=3 keep_last=2"
    assert any(expect in rec.getMessage() for rec in caplog.records)
