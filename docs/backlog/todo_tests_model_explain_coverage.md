# TODO: Tests — Coverage for Model Resolver Explain/Precedence

## Context & Motivation
- Add offline-safe tests for explain semantics and precedence branches.

## Implementation Guidance
- Cases: openai with fake key (missing), `openai-api/lm-studio` with fake key/model, sentinel `none/none`, role-map with provider split, fallback with bare model.

## Scope Definition
- Tests: `tests/unit/inspect_agents/model/test_model_explain.py`.

## Success Criteria
- Deterministic pass with NO_NETWORK=1; asserts on `path` and `*_source` keys.

