# test(iterative): ensure build_iterative_agent forwards retry args to retry shim


import pytest


class SimpleModel:
    async def generate(self, *, input, tools, cache, config):
        # Produce a minimal assistant message
        from inspect_ai.model._chat_message import ChatMessageAssistant
        from inspect_ai.model._model_output import ModelOutput

        return ModelOutput.from_message(ChatMessageAssistant(content="done now", source="generate"))


@pytest.mark.asyncio
async def test_forward_retry_args(monkeypatch):
    captured: dict[str, object] = {}

    # Patch the retry wrapper used by iterative to capture forwarded args
    async def _stub_generate_with_retry_time(model, *, input, tools, cache, config, **kwargs):
        # Record the forwarded retry args
        for k in (
            "max_attempts",
            "initial_backoff_s",
            "max_backoff_s",
            "jitter_s",
            "retry_predicate",
        ):
            captured[k] = kwargs.get(k)

        # Return a trivial output and zero retry wait
        from inspect_ai.model._chat_message import ChatMessageAssistant
        from inspect_ai.model._model_output import ModelOutput

        out = ModelOutput.from_message(ChatMessageAssistant(content="ok", source="generate"))
        return out, 0.0

    import inspect_agents._model_retry as retry_mod

    monkeypatch.setattr(retry_mod, "generate_with_retry_time", _stub_generate_with_retry_time, raising=True)

    from inspect_ai.agent._agent import AgentState

    from inspect_agents.iterative import build_iterative_agent

    agent = build_iterative_agent(
        model=SimpleModel(),
        max_steps=1,
        real_time_limit_sec=1,
        retry_max_attempts=7,
        retry_initial_backoff_s=0.03,
        retry_max_backoff_s=0.5,
        retry_jitter_s=0.01,
        retry_predicate=lambda e: True,
    )

    # Run one iteration to trigger the stubbed retry call
    state = AgentState(messages=[])
    _ = await agent(state)

    assert captured["max_attempts"] == 7
    assert captured["initial_backoff_s"] == 0.03
    assert captured["max_backoff_s"] == 0.5
    assert captured["jitter_s"] == 0.01
    assert callable(captured["retry_predicate"])  # function forwarded
