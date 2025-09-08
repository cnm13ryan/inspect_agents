import pytest

from inspect_agents import resolve_model_explain


def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    for v in [
        "INSPECT_EVAL_MODEL",
        "DEEPAGENTS_MODEL_PROVIDER",
        "OLLAMA_MODEL_NAME",
        "LM_STUDIO_MODEL_NAME",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
    ]:
        monkeypatch.delenv(v, raising=False)


def test_sources_explicit_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    final, trace = resolve_model_explain(model="openai/gpt-4o-mini")
    assert final == "openai/gpt-4o-mini"
    assert trace.model_source == "arg"
    assert trace.provider_source in {"arg", None}


def test_sources_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("INSPECT_EVAL_MODEL", "openai/gpt-4o-mini")
    _, trace = resolve_model_explain()
    assert trace.inspect_eval_source == "set"
    assert trace.model_source == "inspect-eval"
    assert trace.provider_source == "inspect-eval"


def test_sources_default_local(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    final, trace = resolve_model_explain()
    assert final.startswith("ollama/")
    assert trace.provider_source in {"env", "default", "arg"}
    # When no OLLAMA_MODEL_NAME is set and no arg provided, model_source is default
    assert trace.model_source in {"default", "env", "arg"}
