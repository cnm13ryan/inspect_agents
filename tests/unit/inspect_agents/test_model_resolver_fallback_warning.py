import logging


def test_final_fallback_logs_once(monkeypatch, caplog):
    # Ensure a clean env: no explicit model/provider/role mapping
    monkeypatch.delenv("INSPECT_EVAL_MODEL", raising=False)
    monkeypatch.delenv("DEEPAGENTS_MODEL_PROVIDER", raising=False)

    # Import module and reset one-time guard
    import inspect_agents.model as model

    model._OLLAMA_FALLBACK_WARNED = False  # type: ignore[attr-defined]

    # Force the final fallback branch by using an unknown provider
    with caplog.at_level(logging.INFO, logger=model.__name__):
        _ = model.resolve_model(provider="unknown", model=None, role=None)
        _ = model.resolve_model(provider="unknown", model=None, role=None)

    # Exactly one hint should be logged for the fallback
    matches = [r for r in caplog.records if "final_fallback_ollama" in r.getMessage()]
    assert len(matches) == 1
