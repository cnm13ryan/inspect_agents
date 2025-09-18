import asyncio

from inspect_ai.agent._agent import AgentState, agent
from inspect_ai.model._chat_message import ChatMessageAssistant, ChatMessageUser
from inspect_ai.util._store import Store, init_subtask_store
from inspect_ai.util._store_model import store_as

from inspect_agents.migration import create_deep_agent
from inspect_agents.state import Todos
from inspect_agents.tools import read_file


@agent
def model_calls_todos_and_write():
    async def execute(state: AgentState, tools):
        # Write a todo and a file, then submit
        state.messages.append(
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
                    {
                        "id": "3",
                        "function": "submit",
                        "arguments": {"answer": "OK"},
                    },
                ],
            )
        )
        return state

    return execute


def test_create_deep_agent_minimal_flow():
    # Isolate store
    s = Store()
    init_subtask_store(s)

    agent_obj = create_deep_agent(tools=[], instructions="You are helpful.", model=model_calls_todos_and_write())

    result = asyncio.run(agent_obj(AgentState(messages=[ChatMessageUser(content="start")])))
    assert "OK" in (result.output.completion or "")

    # Verify file write via read_file tool
    rf = read_file()
    out = asyncio.run(rf(file_path="a.txt", offset=0, limit=1))
    assert out.strip().endswith("hello")

    # Verify todos updated in Store
    todos = store_as(Todos).get_todos()
    assert any(t.content == "do x" for t in todos)


def test_create_deep_agent_respects_include_defaults(monkeypatch):
    captured: dict[str, object] = {}

    def fake_resolver(names, *, include_defaults):
        captured["include_defaults"] = include_defaults
        return []

    monkeypatch.setattr("inspect_agents.migration._resolve_builtin_tools", fake_resolver)

    async def _dummy_agent(state):  # pragma: no cover - stub only
        return state

    def fake_react(**kwargs):
        captured.update(kwargs)
        return _dummy_agent

    monkeypatch.setattr("inspect_ai.agent._react.react", fake_react)

    agent_obj = create_deep_agent(tools=[], instructions="Hello", include_defaults=False)

    assert callable(agent_obj)
    assert captured["include_defaults"] is False
    assert captured["tools"] == []
    prompt = captured["prompt"]
    assert "Todo & Filesystem Tools" not in prompt
