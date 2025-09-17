"""Shared helper utilities for the iterative agent runtime."""

from __future__ import annotations

import logging
import time
from typing import Any

# Preserve historical logger name for downstream log routing/tests
logger = logging.getLogger("inspect_agents.iterative")


def _remaining_timeout(
    start: float,
    limit_sec: int | None,
    total_retry_time: float,
    productive_time_enabled: bool,
    *,
    now: float | None = None,
) -> int | None:
    """Compute remaining per-call timeout in seconds.

    Returns None when no overall limit is set; otherwise clamps to at least 1s.
    Pass `now` from the injected `clock()` for test determinism.
    """
    if limit_sec is None:
        return None
    if now is None:
        now = time.time()
    wall = float(now - start)
    elapsed = wall - total_retry_time if productive_time_enabled else wall
    remaining = int(limit_sec - elapsed)
    return max(1, remaining) if remaining > 0 else 1


def _should_emit_progress(step: int, every: int | None) -> bool:
    """Return True when a progress ping should be emitted for this step."""
    try:
        return bool(every) and step % int(every) == 0
    except Exception:
        return False


def _append_overflow_hint(messages: list[object]) -> None:
    """Append the standard overflow hint message to the conversation."""
    from inspect_ai.model._chat_message import ChatMessageUser

    try:
        from ._conversation import _OVERFLOW_HINT  # type: ignore

        hint: str = str(_OVERFLOW_HINT)
    except Exception:
        hint = "Context too long; please summarize recent steps and continue."

    messages.append(ChatMessageUser(content=hint))


def _prune_with_debug(
    messages: list[object],
    *,
    keep_last: int,
    token_cap: int | None,
    last_k: int,
    debug: bool,
    reason: str = "threshold",
    threshold: int | None = None,
    tokenizer: Any | None = None,
) -> list[object]:
    """Apply token-aware truncation (optional) then prune tail, with debug logs."""
    try:
        from ._conversation import prune_messages as _prune
        from ._conversation import truncate_conversation_tokens as _truncate
    except Exception:  # pragma: no cover - defensive fallback
        _prune = None  # type: ignore
        _truncate = None  # type: ignore

    try:
        if _truncate is not None and token_cap is not None:
            size_pre = len(messages)
            messages = _truncate(
                messages,
                max_tokens_per_msg=int(token_cap),
                last_k=int(last_k),
                tokenizer=tokenizer,
            )
            if debug:
                logger.info(
                    "Truncate: reason=%s size_pre=%d last_k=%d cap=%d",
                    reason,
                    size_pre,
                    int(last_k),
                    int(token_cap),
                )
    except Exception:
        pass

    pre_len = len(messages)
    if _prune is not None:
        try:
            messages = _prune(messages, keep_last=int(keep_last))
            if debug:
                if reason == "threshold":
                    logger.info(
                        "Prune: reason=threshold pre=%d post=%d keep_last=%d threshold=%s",
                        pre_len,
                        len(messages),
                        int(keep_last),
                        "None" if threshold is None else int(threshold),
                    )
                else:
                    logger.info(
                        "Prune: reason=overflow pre=%d post=%d keep_last=%d",
                        pre_len,
                        len(messages),
                        int(keep_last),
                    )
        except Exception:
            pass

    return messages


__all__ = [
    "_remaining_timeout",
    "_should_emit_progress",
    "_append_overflow_hint",
    "_prune_with_debug",
]
