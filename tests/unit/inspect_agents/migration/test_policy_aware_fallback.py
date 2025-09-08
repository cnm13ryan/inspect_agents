import asyncio

import pytest
from inspect_ai.model._chat_message import ChatMessageAssistant, ChatMessageUser

from inspect_agents.migration import _apply_side_effect_calls


def test_skip_fallback_on_approval_denial(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    # Stub execute_tools to raise an approval denial signal
    import sys
    import types

    mod_name = "inspect_ai.model._call_tools"
    sys.modules.pop(mod_name, None)
    fake = types.ModuleType(mod_name)

    class DeniedError(Exception):
        def __init__(self, message: str = "ApprovalDenied") -> None:  # noqa: D401
            super().__init__(message)
            self.type = "approval_denied"
            self.message = message

    async def execute_tools(_msgs, _tools):  # type: ignore[no-redef]
        raise DeniedError()

    fake.execute_tools = execute_tools  # type: ignore[attr-defined]
    sys.modules[mod_name] = fake

    caplog.set_level("DEBUG", logger="inspect_agents.migration")

    messages = [
        ChatMessageUser(content="start"),
        ChatMessageAssistant(
            content="",
            tool_calls=[
                {"id": "1", "function": "write_file", "arguments": {"file_path": "d.txt", "content": "deny"}},
                {"id": "2", "function": "submit", "arguments": {"answer": "OK"}},
            ],
        ),
    ]

    async def run() -> None:
        await _apply_side_effect_calls(messages, [])

    asyncio.run(run())

    # Ensure no fallback writes occurred
    from inspect_ai.util._store_model import store_as

    from inspect_agents.state import Files

    assert store_as(Files).get_file("d.txt") is None

    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "approval_denied" in logs
