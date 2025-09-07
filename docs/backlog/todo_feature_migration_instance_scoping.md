# TODO: Side‑Effect Helper — Instance Scoping for Store Models

## Context & Motivation
- Fallbacks write to the default Store instance; multi‑agent runs may require isolation.

## Implementation Guidance
- Accept optional `instance` and pass through to `store_as(Files, instance=...)` and `store_as(Todos, instance=...)`.
- Default to current behavior when `instance` is None.

## Scope Definition
- Code: `src/inspect_agents/migration.py`.
- Tests: verify isolation across two instances and default behavior unchanged.

## Success Criteria
- Optional per‑agent instance scoping supported with tests.
