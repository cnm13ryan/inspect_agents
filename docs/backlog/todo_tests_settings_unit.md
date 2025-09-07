# TODO: Tests — Unit Coverage for `settings.py`

## Context & Motivation
- Helpers are covered indirectly; add direct unit tests to pin semantics and prevent drift.

## Implementation Guidance
- Add `tests/unit/inspect_agents/config/test_settings.py` covering: `truthy`, `int_env` (min/max and invalid), `float_env`, `str_env` (empty vs unset), `typed_results_enabled`, `default_tool_timeout`.

## Scope Definition
- Tests only; no behavior change.

## Success Criteria
- New tests pass offline deterministically.

