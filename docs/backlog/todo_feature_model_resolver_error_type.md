# TODO: Model Resolver — Typed Error with `.explain`

## Context & Motivation
- Replace generic `RuntimeError` with a typed `ModelResolutionError` that carries `.explain` and `.reason` without changing `resolve_model()` return type.

## Implementation Guidance
- Define `ModelResolutionError(Exception)` with fields; raise it for missing API key/model/vendor cases.
- Keep human‑readable message; tests assert `.reason` and `.explain` content.

## Scope Definition
- Code: `src/inspect_agents/model.py`.
- Tests: augment model tests; ensure offline determinism.

## Success Criteria
- Typed errors emitted with structured context; tests pass.

## Status
- DONE (2025-09-07)
- Implemented `ResolveModelError` carrying `.trace` and `.final_step`; `resolve_model(...)` continues to raise `RuntimeError` for backward compatibility while `resolve_model_explain(...)` raises `ResolveModelError`.
- References:
  - Code: `src/inspect_agents/model.py`
  - Tests: `tests/inspect_agents/test_model_resolver.py`
  - Docs: `docs/how-to/model_resolver_explain.md`
