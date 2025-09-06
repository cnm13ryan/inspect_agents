# test(retry): arg overrides for deterministic control

import types

import pytest


class _FlakyModel:
    def __init__(self, fails: int):
        self._n = int(fails)

    async def generate(self, *, input, tools, cache, config):
        if self._n > 0:
            self._n -= 1
            raise TimeoutError("retryable")
        return types.SimpleNamespace(message=types.SimpleNamespace(content="ok"))


@pytest.mark.asyncio
async def test_args_override_env_accumulates_sleep(monkeypatch):
    # Force fallback path without patching private module state
    monkeypatch.setenv("INSPECT_RETRY_DISABLE_TENACITY", "1")

    # Set conflicting env that should be ignored when args are provided
    monkeypatch.setenv("INSPECT_RETRY_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("INSPECT_RETRY_INITIAL_SECONDS", "0.5")
    monkeypatch.setenv("INSPECT_RETRY_MAX_SECONDS", "1.0")
    monkeypatch.setenv("INSPECT_RETRY_JITTER", "0.3")

    from inspect_agents._model_retry import generate_with_retry_time

    # With fails=3 and overrides initial=0.01, max=0.04 we expect delays:
    # 0.01 + 0.02 + 0.04 = 0.07 seconds total
    model = _FlakyModel(fails=3)
    out, sleep_s = await generate_with_retry_time(
        model,
        input=[],
        tools=[],
        cache=False,
        config=None,
        max_attempts=6,
        initial_backoff_s=0.01,
        max_backoff_s=0.04,
        jitter_s=0.0,
    )
    assert getattr(out, "message", None) is not None
    assert sleep_s == pytest.approx(0.07, rel=1e-6, abs=1e-9)


@pytest.mark.asyncio
async def test_args_max_attempts_limits_retries(monkeypatch):
    # Force fallback path without patching private module state
    monkeypatch.setenv("INSPECT_RETRY_DISABLE_TENACITY", "1")

    from inspect_agents._model_retry import generate_with_retry_time

    # fails=2 would succeed on the 3rd attempt; max_attempts=2 should raise
    model = _FlakyModel(fails=2)
    with pytest.raises(TimeoutError):
        await generate_with_retry_time(
            model,
            input=[],
            tools=[],
            cache=False,
            config=None,
            max_attempts=2,
            initial_backoff_s=0.001,
            max_backoff_s=0.001,
            jitter_s=0.0,
        )
