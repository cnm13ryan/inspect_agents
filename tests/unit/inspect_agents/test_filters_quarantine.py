import json

import pytest
from inspect_ai.model._chat_message import ChatMessageSystem, ChatMessageUser
from inspect_ai.util._store import Store, init_subtask_store, store

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


@pytest.mark.asyncio
async def test_inherit_strict_mode_from_store_when_enabled(monkeypatch):
    """When inheritance is enabled, a pre-set store mode should cascade.

    - Pre-seed Store with ACTIVE_INPUT_FILTER_KEY="strict"
    - Global env is "off" to prove inheritance takes precedence
    - Result should be strictly filtered to the last user message
    - Active mode remains recorded as "strict"
    """
    _fresh_store()
    monkeypatch.setenv("INSPECT_QUARANTINE_INHERIT", "1")
    monkeypatch.setenv("INSPECT_QUARANTINE_MODE", "off")

    # Pre-seed parent mode in the Store
    store().set(ACTIVE_INPUT_FILTER_KEY, "strict")

    # Build messages including assistant with tool_calls (should be stripped)
    from inspect_ai.model._chat_message import ChatMessageAssistant
    from inspect_ai.tool import ToolCall

    messages = [
        ChatMessageSystem(content="sys"),
        ChatMessageUser(content="one"),
        ChatMessageAssistant(content="tooly", tool_calls=[ToolCall(id="a", function="x", arguments={})]),
        ChatMessageUser(content="final"),
    ]

    filt = default_input_filter("child")
    result = await filt(messages)

    # Strict filter yields only the last message (content-only)
    assert len(result) == 1
    assert isinstance(result[0], ChatMessageUser)
    assert result[0].text == "final"
    # Mode remains recorded
    assert store().get(ACTIVE_INPUT_FILTER_KEY) == "strict"


@pytest.mark.asyncio
async def test_scoped_summary_caps_trim_bytes_todos_files(monkeypatch, caplog):
    """Scoped summary respects caps and trims to byte budget with logging.

    - Set tiny byte cap and small item caps
    - Seed store with many todos/files
    - Verify JSON summary reflects caps and final size <= byte cap
    - Optionally assert a trimming log line is emitted
    """
    _fresh_store()
    # Force scoped via per-agent override
    monkeypatch.setenv("INSPECT_QUARANTINE_MODE__researcher", "scoped")
    monkeypatch.setenv("INSPECT_QUARANTINE_MODE", "strict")
    # Small caps so trimming must occur
    monkeypatch.setenv("INSPECT_SCOPED_MAX_BYTES", "120")
    monkeypatch.setenv("INSPECT_SCOPED_MAX_TODOS", "2")
    monkeypatch.setenv("INSPECT_SCOPED_MAX_FILES", "2")

    # Seed store models with oversized data
    from inspect_ai.util._store_model import store_as

    from inspect_agents.state import Files, Todo, Todos

    todos_model = store_as(Todos)
    files_model = store_as(Files)

    todos = [Todo(content="x" * 300, status="pending") for _ in range(5)]
    todos_model.set_todos(todos)
    for i in range(5):
        files_model.put_file(f"file_{i}.txt", "data" * 50)

    # Capture logs from filters module
    caplog.set_level("INFO", logger="inspect_agents.filters")

    filt = default_input_filter("researcher")
    base = [ChatMessageUser(content="hi")]
    result = await filt(base)

    # Find the appended JSON summary
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

    assert json_msg is not None, "scoped summary JSON should be appended"

    # Respect item caps (could be further trimmed for byte cap)
    assert len(json_msg.get("files", {}).get("list", [])) <= 2
    assert len(json_msg.get("todos", [])) <= 2

    # Respect byte cap (min clamp is 512 per filter implementation)
    size = len(json.dumps(json_msg, ensure_ascii=False).encode("utf-8"))
    assert size <= 512

    # Log includes trimming indicator (best-effort; don't fail if logging disabled)
    trimmed_lines = [m for m in caplog.messages if "scoped_summary" in m]
    assert any("trimmed=True" in m for m in trimmed_lines), trimmed_lines
