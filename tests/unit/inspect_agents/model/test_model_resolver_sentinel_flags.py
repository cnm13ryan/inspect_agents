import pytest

from inspect_agents import resolve_model_explain


@pytest.mark.parametrize("sentinel", ["none/none", "NONE/NONE", " none/none ", "None/None"])
def test_sentinel_flags(monkeypatch: pytest.MonkeyPatch, sentinel: str) -> None:
    # Clear common env
    for var in [
        "INSPECT_EVAL_MODEL",
        "DEEPAGENTS_MODEL_PROVIDER",
        "OLLAMA_MODEL_NAME",
        "LM_STUDIO_MODEL_NAME",
    ]:
        monkeypatch.delenv(var, raising=False)

    monkeypatch.setenv("INSPECT_EVAL_MODEL", sentinel)

    final, trace = resolve_model_explain()
    # Should resolve to local path (ollama or final_fallback)
    assert final.startswith("ollama/")
    # Flags should reflect sentinel handling
    assert trace.inspect_eval_disabled is True
    assert trace.env_inspect_eval_model_raw == "none/none"
