# TODO: Settings — Iterative Helpers Wrap `settings.int_env`

## Context & Motivation
- `iterative_config._parse_int_opt` semantics differ slightly from `settings.int_env`; prefer central parsing with wrappers to preserve <=0 → None.

## Implementation Guidance
- Add tiny wrappers in `iterative_config.py` that call `settings.int_env` then convert `<=0` → None; adopt them for time/step/pruning/truncation.

## Scope Definition
- Code: `src/inspect_agents/iterative_config.py`.
- Tests: existing iterative tests should remain green; optionally add a unit test for wrapper semantics.

## Success Criteria
- Delegation in place; behavior unchanged for disabled/empty values.
