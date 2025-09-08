import pytest

from inspect_agents import resolve_model_explain

ALLOWED_LABELS = {
    "explicit_model_with_provider",
    "role_env_mapping",
    "role_inspect_indirection",
    "env_INSPECT_EVAL_MODEL",
    "provider_ollama",
    "provider_lm_studio",
    # Remote providers (subset used in tests)
    "provider_openai",
    "provider_openai_api_lm-studio",
    "fallback_model_with_provider",
    "final_fallback_ollama",
}


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in [
        "INSPECT_EVAL_MODEL",
        "DEEPAGENTS_MODEL_PROVIDER",
        "OLLAMA_MODEL_NAME",
        "LM_STUDIO_MODEL_NAME",
    ]:
        monkeypatch.delenv(var, raising=False)
    for var in [
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "LM_STUDIO_API_KEY",
        "LM_STUDIO_MODEL",
    ]:
        monkeypatch.delenv(var, raising=False)
    for role in ["CODER", "RESEARCHER", "EDITOR", "GRADER"]:
        monkeypatch.delenv(f"INSPECT_ROLE_{role}_MODEL", raising=False)
        monkeypatch.delenv(f"INSPECT_ROLE_{role}_PROVIDER", raising=False)


def test_label_explicit_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    final, trace = resolve_model_explain(model="openai/gpt-4o-mini")
    assert final == "openai/gpt-4o-mini"
    assert trace.steps[-1].path in ALLOWED_LABELS


def test_label_role_indirection(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    _, trace = resolve_model_explain(role="coder")
    assert trace.steps[-1].path in ALLOWED_LABELS


def test_label_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("INSPECT_EVAL_MODEL", "openai/gpt-4o-mini")
    _, trace = resolve_model_explain()
    assert trace.steps[-1].path in ALLOWED_LABELS


def test_label_default_or_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    # No provider/model/role -> prefer ollama or final fallback
    _, trace = resolve_model_explain()
    assert trace.steps[-1].path in ALLOWED_LABELS


def test_label_openai_api_vendor(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("LM_STUDIO_API_KEY", "x")
    monkeypatch.setenv("LM_STUDIO_MODEL", "local-model")
    _, trace = resolve_model_explain(provider="openai-api/lm-studio")
    assert trace.steps[-1].path in ALLOWED_LABELS


def test_label_fallback_with_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    _, trace = resolve_model_explain(provider="acme", model="foo-bar")
    assert trace.steps[-1].path in ALLOWED_LABELS
