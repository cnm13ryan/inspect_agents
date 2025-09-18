from inspect_agents.agents import build_supervisor
from inspect_agents.iterative import build_iterative_agent


def test_build_supervisor_include_defaults_false_skips_builtin_tools(monkeypatch):
    def raising_builtins():
        raise AssertionError("_built_in_tools should not run when include_defaults is False")

    monkeypatch.setattr("inspect_agents.agents._built_in_tools", raising_builtins)

    captured: dict[str, object] = {}

    async def _dummy_agent(state):  # pragma: no cover - stub only
        return state

    def fake_react(**kwargs):
        captured.update(kwargs)
        return _dummy_agent

    monkeypatch.setattr("inspect_ai.agent._react.react", fake_react)

    sentinel = object()
    agent_obj = build_supervisor(prompt="Base", tools=[sentinel], include_defaults=False)

    assert captured.get("tools") == [sentinel]
    prompt = captured.get("prompt", "")
    assert isinstance(prompt, str)
    assert "Todo & Filesystem Tools" not in prompt
    assert "You have access to a number of tools." in prompt
    assert agent_obj is _dummy_agent


def test_build_iterative_agent_include_defaults_false_skips_base_tools(monkeypatch):
    def raising_base_tools(**_):
        raise AssertionError("_base_tools should not run when include_defaults is False")

    monkeypatch.setattr("inspect_agents.iterative._base_tools", raising_base_tools)

    captured: dict[str, object] = {}

    def fake_default_system_message(*, code_only: bool, include_defaults: bool) -> str:
        captured["system_include_defaults"] = include_defaults
        captured["code_only"] = code_only
        return "prompt"

    monkeypatch.setattr(
        "inspect_agents.iterative._default_system_message",
        fake_default_system_message,
    )

    def identity_agent(*, name=None):  # noqa: ARG001 - signature parity
        def decorator(fn):
            captured["iterative_fn"] = fn
            return fn

        return decorator

    monkeypatch.setattr("inspect_ai.agent._agent.agent", identity_agent)

    sentinel = object()
    agent_obj = build_iterative_agent(include_defaults=False, tools=[sentinel])

    assert callable(agent_obj)
    assert captured["system_include_defaults"] is False
    fn = captured["iterative_fn"]
    assert fn is not None
    closure_cells = fn.__closure__ or ()
    freevars = fn.__code__.co_freevars
    closure = {name: cell.cell_contents for name, cell in zip(freevars, closure_cells)}
    assert closure["active_tools"] == [sentinel]
