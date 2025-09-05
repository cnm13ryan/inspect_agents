import asyncio
import json

import pytest

from inspect_ai.util._store import Store, init_subtask_store, store
from inspect_ai.model._chat_message import ChatMessageSystem, ChatMessageUser

from inspect_agents.filters import (
    ACTIVE_INPUT_FILTER_KEY,
    default_input_filter,
)


def _fresh_store() -> Store:
    s = Store()
    init_subtask_store(s)
    return s


@pytest.mark.asyncio
async def test_per_agent_override_scoped_adds_summary_and_records_mode(monkeypatch):
    """Per-agent env override must win and append scoped JSON summary.

    - Sets INSPECT_QUARANTINE_MODE__researcher=scoped
    - Applies default_input_filter("researcher") to a small message list
    - Asserts a JSON summary user message is appended and active mode is recorded
    """
    _fresh_store()

    # Global default is strict, but per-agent override should win
    monkeypatch.setenv("INSPECT_QUARANTINE_MODE", "strict")
    monkeypatch.setenv("INSPECT_QUARANTINE_MODE__researcher", "scoped")

    # Build the filter for the agent and apply it
    filt = default_input_filter("researcher")

    messages = [
        ChatMessageSystem(content="system"),
        ChatMessageUser(content="hello"),
    ]

    result = await filt(messages)

    # There should be a JSON summary message appended
    json_msg = None
    for m in result:
        if isinstance(m, ChatMessageUser):
            try:
                parsed = json.loads(m.text)
                if isinstance(parsed, dict) and parsed.get("scope") == "scoped":
                    json_msg = parsed
                    break
            except Exception:
                continue

    assert json_msg is not None, "scoped summary JSON should be appended by the filter"
    assert json_msg.get("version") == "v1"
    assert "todos" in json_msg and "files" in json_msg

    # The chosen mode should be recorded into the Store for inheritance
    assert store().get(ACTIVE_INPUT_FILTER_KEY) == "scoped"
