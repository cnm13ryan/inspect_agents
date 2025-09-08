import asyncio

from inspect_ai.model._chat_message import ChatMessageAssistant, ChatMessageUser
from inspect_ai.util._store_model import store_as

from inspect_agents.migration import _apply_side_effect_calls
from inspect_agents.state import Files, Todos


def test_fallback_writes_to_specified_instance() -> None:
    messages = [
        ChatMessageUser(content="start"),
        ChatMessageAssistant(
            content="",
            tool_calls=[
                {"id": "1", "function": "write_file", "arguments": {"file_path": "i.txt", "content": "scoped"}},
                {
                    "id": "2",
                    "function": "write_todos",
                    "arguments": {"todos": [{"content": "task", "status": "pending"}]},
                },
                {"id": "3", "function": "submit", "arguments": {"answer": "OK"}},
            ],
        ),
    ]

    async def run() -> None:
        # Force fallback path by passing empty tools and specify an instance
        await _apply_side_effect_calls(messages, [], instance="agentA")

    asyncio.run(run())

    # Writes should appear under the specified instance only
    assert store_as(Files, instance="agentA").get_file("i.txt") == "scoped"
    assert store_as(Files).get_file("i.txt") is None

    todos_scoped = store_as(Todos, instance="agentA").get_todos()
    assert any(t.content == "task" for t in todos_scoped)
    todos_default = store_as(Todos).get_todos()
    assert not any(t.content == "task" for t in todos_default)
