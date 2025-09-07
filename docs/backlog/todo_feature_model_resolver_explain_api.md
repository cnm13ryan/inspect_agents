# TODO: Model Resolver — Implement `resolve_model_explain(...)`

## Context & Motivation
- Provide a structured `(model_id, explain_dict)` surface for deterministic testing and debugging (avoid brittle log scraping).

## Implementation Guidance
- Add `resolve_model_explain(provider=None, model=None, role=None) -> tuple[str, dict]` delegating to `_resolve_model_core(...)`.
- Include enriched fields: `provider_effective`, `provider_source`, `model_effective`, `model_source`, `role`, plus existing inputs and `path`.

## Scope Definition
- Code: `src/inspect_agents/model.py`.
- Tests: add `tests/unit/inspect_agents/model/test_model_explain.py` covering explicit, role‑map, `INSPECT_EVAL_MODEL`, and provider branches.
- Docs: reference note in `docs/reference/environment.md`.

## Success Criteria
- Deterministic tests pass offline; explain dict stable and documented.

