import asyncio

import pytest
from inspect_ai.model._chat_message import ChatMessageAssistant, ChatMessageUser

from inspect_agents.migration import _apply_side_effect_calls


def test_fallback_respects_size_limit(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    # Enforce a small max bytes to trigger the guard
    monkeypatch.setenv("INSPECT_AGENTS_FS_MAX_BYTES", "16")

    # Oversize content (>16 bytes)
    big_content = "x" * 32

    messages = [
        ChatMessageUser(content="start"),
        ChatMessageAssistant(
            content="",
            tool_calls=[
                {
                    "id": "1",
                    "function": "write_file",
                    "arguments": {"file_path": "big.txt", "content": big_content},
                },
                {"id": "2", "function": "submit", "arguments": {"answer": "OK"}},
            ],
        ),
    ]

    caplog.set_level("DEBUG", logger="inspect_agents.migration")

    async def run() -> None:
        await _apply_side_effect_calls(messages, [])

    asyncio.run(run())

    # Verify the guard log is present and no write occurred
    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "fallback_file_too_large" in logs

    from inspect_ai.util._store_model import store_as

    from inspect_agents.state import Files

    # The file should not be present due to size guard
    assert store_as(Files).get_file("big.txt") is None
