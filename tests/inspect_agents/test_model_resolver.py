import pytest

from inspect_agents import (
    ResolveModelError,
    resolve_model,
    resolve_model_explain,
)


def _clear_common_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Generic knobs
    for var in [
        "INSPECT_EVAL_MODEL",
        "DEEPAGENTS_MODEL_PROVIDER",
        "OLLAMA_MODEL_NAME",
        "LM_STUDIO_MODEL_NAME",
    ]:
        monkeypatch.delenv(var, raising=False)

    # Remote providers
    for var in [
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GROQ_API_KEY",
        "MISTRAL_API_KEY",
        "PERPLEXITY_API_KEY",
        "FIREWORKS_API_KEY",
        "GROK_API_KEY",
        "GOODFIRE_API_KEY",
        "OPENROUTER_API_KEY",
        # OpenAI-compatible vendors
        "LM_STUDIO_API_KEY",
        "LM_STUDIO_MODEL",
    ]:
        monkeypatch.delenv(var, raising=False)

    # Role mapping (clear any prior settings)
    for role in ["CODER", "RESEARCHER", "EDITOR", "GRADER"]:
        monkeypatch.delenv(f"INSPECT_ROLE_{role}_MODEL", raising=False)
        monkeypatch.delenv(f"INSPECT_ROLE_{role}_PROVIDER", raising=False)


def test_explicit_provider_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_common_env(monkeypatch)
    final, trace = resolve_model_explain(model="openai/gpt-4o-mini")
    assert final == "openai/gpt-4o-mini"
    assert trace.final == final
    assert trace.steps[-1].path == "explicit_model_with_provider"


def test_role_mapping_no_env_returns_inspect_role(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_common_env(monkeypatch)
    final, trace = resolve_model_explain(role="coder")
    assert final == "inspect/coder"
    assert trace.steps[-1].path == "role_inspect_indirection"


def test_role_mapping_with_env_provider_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_common_env(monkeypatch)
    monkeypatch.setenv("INSPECT_ROLE_CODER_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("INSPECT_ROLE_CODER_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    final, trace = resolve_model_explain(role="coder")
    assert final == "openai/gpt-4o-mini"
    # Should have a role mapping step and end on provider_openai
    assert any(s.path == "role_env_mapping" for s in trace.steps)
    assert trace.steps[-1].path == "provider_openai"


def test_env_inspect_eval_model_override_and_sentinel(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_common_env(monkeypatch)
    monkeypatch.setenv("INSPECT_EVAL_MODEL", "openai/gpt-4o-mini")
    final, trace = resolve_model_explain()
    assert final == "openai/gpt-4o-mini"
    assert trace.steps[-1].path == "env_INSPECT_EVAL_MODEL"

    # Sentinel disables the override
    _clear_common_env(monkeypatch)
    monkeypatch.setenv("INSPECT_EVAL_MODEL", "none/none")
    final2, trace2 = resolve_model_explain()
    assert final2.startswith("ollama/")
    assert trace2.steps[-1].path in {"provider_ollama", "final_fallback_ollama"}


def test_provider_only_with_env_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_common_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    final, trace = resolve_model_explain(provider="openai")
    assert final == "openai/gpt-4o-mini"
    assert trace.steps[-1].path == "provider_openai"


def test_openai_api_vendor(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_common_env(monkeypatch)
    monkeypatch.setenv("LM_STUDIO_API_KEY", "x")
    monkeypatch.setenv("LM_STUDIO_MODEL", "qwen3")
    final, trace = resolve_model_explain(provider="openai-api/lm-studio")
    assert final == "openai-api/lm-studio/qwen3"
    assert trace.steps[-1].path == "provider_openai_api_lm-studio"


def test_missing_key_raises_resolve_model_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_common_env(monkeypatch)
    with pytest.raises(ResolveModelError) as ei:
        resolve_model_explain(provider="openai")
    assert "requires OPENAI_API_KEY" in str(ei.value)
    assert ei.value.trace.steps[-1].path == "provider_openai"


def test_missing_model_tag_raises_resolve_model_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_common_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    with pytest.raises(ResolveModelError) as ei:
        resolve_model_explain(provider="openai")
    assert "Model not specified for provider 'openai'" in str(ei.value)
    assert ei.value.trace.steps[-1].path == "provider_openai"


def test_role_mapping_full_path_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_common_env(monkeypatch)
    # Full provider/model path in role mapping; only API key needed
    monkeypatch.setenv("INSPECT_ROLE_CODER_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    final, trace = resolve_model_explain(role="coder")
    assert final == "openai/gpt-4o-mini"
    assert any(s.path == "role_env_mapping" for s in trace.steps)
    assert trace.steps[-1].path == "provider_openai"


def test_role_mapping_full_path_openai_api_vendor(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_common_env(monkeypatch)
    # Role mapping provides full vendor path; only vendor API key needed
    monkeypatch.setenv("INSPECT_ROLE_CODER_MODEL", "openai-api/lm-studio/qwen3")
    monkeypatch.setenv("LM_STUDIO_API_KEY", "x")
    final, trace = resolve_model_explain(role="coder")
    assert final == "openai-api/lm-studio/qwen3"
    assert any(s.path == "role_env_mapping" for s in trace.steps)
    assert trace.steps[-1].path == "provider_openai_api_lm-studio"


@pytest.mark.parametrize("sentinel", ["None/None", " none/none ", "NONE/NONE"])
def test_env_inspect_eval_model_sentinel_variants(monkeypatch: pytest.MonkeyPatch, sentinel: str) -> None:
    _clear_common_env(monkeypatch)
    monkeypatch.setenv("INSPECT_EVAL_MODEL", sentinel)
    final, trace = resolve_model_explain()
    assert final.startswith("ollama/")
    assert trace.steps[-1].path in {"provider_ollama", "final_fallback_ollama"}


def test_openai_api_vendor_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_common_env(monkeypatch)
    # Provide a model tag so the error is strictly about the missing key
    with pytest.raises(ResolveModelError) as ei:
        resolve_model_explain(provider="openai-api/lm-studio", model="qwen3")
    assert "requires LM_STUDIO_API_KEY" in str(ei.value)
    assert ei.value.trace.steps[-1].path == "provider_openai_api_lm-studio"


def test_openai_api_vendor_missing_model_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_common_env(monkeypatch)
    monkeypatch.setenv("LM_STUDIO_API_KEY", "x")
    with pytest.raises(ResolveModelError) as ei:
        resolve_model_explain(provider="openai-api/lm-studio")
    assert "Model not specified for provider 'openai-api/lm-studio'" in str(ei.value)
    assert ei.value.trace.steps[-1].path == "provider_openai_api_lm-studio"


def test_resolve_model_wrapper_raises_runtimeerror(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_common_env(monkeypatch)
    with pytest.raises(RuntimeError) as ei:
        resolve_model(provider="openai")
    assert "requires OPENAI_API_KEY" in str(ei.value)


def test_fallback_model_with_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_common_env(monkeypatch)
    final, trace = resolve_model_explain(provider="acme", model="foo-bar")
    assert final == "acme/foo-bar"
    assert trace.steps[-1].path == "fallback_model_with_provider"
