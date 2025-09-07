# TODO: Tests — Coverage for Model Resolver Explain/Precedence

## Context & Motivation
- Add offline-safe tests for explain semantics and precedence branches.

## Implementation Guidance
- Cases: openai with fake key (missing), `openai-api/lm-studio` with fake key/model, sentinel `none/none`, role-map with provider split, fallback with bare model.

## Scope Definition
- Tests: implemented in `tests/inspect_agents/test_model_resolver.py` (covers explicit provider/model, role mapping, `INSPECT_EVAL_MODEL` override and sentinel, OpenAI‑compatible vendor path, missing key/model errors, fallback with bare model, and wrapper RuntimeError behavior).

## Success Criteria
- Deterministic pass with NO_NETWORK=1; asserts on `path` and `*_source` keys.

## Status
- DONE (2025-09-07)
