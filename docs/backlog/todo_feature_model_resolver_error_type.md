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

