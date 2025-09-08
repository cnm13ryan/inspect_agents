import asyncio

import pytest
from inspect_ai.model._chat_message import ChatMessageAssistant, ChatMessageUser

from inspect_agents.migration import _apply_side_effect_calls


def test_fallback_logging_emitted(caplog: pytest.LogCaptureFixture) -> None:
    # Build a minimal conversation where assistant proposes side-effect tools + submit
    messages = [
        ChatMessageUser(content="start"),
        ChatMessageAssistant(
            content="",
            tool_calls=[
                {
                    "id": "1",
                    "function": "write_todos",
                    "arguments": {"todos": [{"content": "do x", "status": "pending"}]},
                },
                {
                    "id": "2",
                    "function": "write_file",
                    "arguments": {"file_path": "a.txt", "content": "hello"},
                },
                {"id": "3", "function": "submit", "arguments": {"answer": "OK"}},
            ],
        ),
    ]

    caplog.set_level("DEBUG", logger="inspect_agents.migration")

    async def run() -> None:
        # Pass no tools to force fallback application path
        await _apply_side_effect_calls(messages, [])

    asyncio.run(run())

    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "side_effects.fallback_begin" in logs
    assert "side_effects.fallback_done" in logs


def test_execute_tools_success_skips_fallback(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Fake execute_tools that applies side effects directly
    import sys
    import types

    mod_name = "inspect_ai.model._call_tools"
    sys.modules.pop(mod_name, None)
    fake = types.ModuleType(mod_name)

    async def execute_tools(_msgs, _tools):  # type: ignore[no-redef]
        from inspect_ai.util._store_model import store_as

        from inspect_agents.state import Files, Todo, Todos

        # Apply the same mutations that fallback would apply
        files = store_as(Files)
        files.put_file("b.txt", "world")
        todos = store_as(Todos)
        todos.set_todos([Todo(content="do y", status="pending")])

    fake.execute_tools = execute_tools  # type: ignore[attr-defined]
    sys.modules[mod_name] = fake

    caplog.set_level("DEBUG", logger="inspect_agents.migration")

    from inspect_ai.util._store import Store, init_subtask_store
    from inspect_ai.util._store_model import store_as

    from inspect_agents.state import Files, Todos

    s = Store()
    init_subtask_store(s)

    messages = [
        ChatMessageUser(content="start"),
        ChatMessageAssistant(
            content="",
            tool_calls=[
                {"id": "1", "function": "write_file", "arguments": {"file_path": "b.txt", "content": "world"}},
                {
                    "id": "2",
                    "function": "write_todos",
                    "arguments": {"todos": [{"content": "do y", "status": "pending"}]},
                },
                {"id": "3", "function": "submit", "arguments": {"answer": "OK"}},
            ],
        ),
    ]

    async def run() -> None:
        await _apply_side_effect_calls(messages, [])

    asyncio.run(run())

    # Store has expected values from our execute_tools stub
    assert store_as(Files).get_file("b.txt") == "world"
    assert any(t.content == "do y" for t in store_as(Todos).get_todos())

    # Fallback should find nothing pending; wrote_* should be zero
    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "side_effects.fallback_done" in logs
    assert "wrote_files=0" in logs
    assert "wrote_todos=0" in logs
