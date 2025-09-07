# TODO: Model Resolver — Explicit Sentinel Handling for `INSPECT_EVAL_MODEL=none/none`

## Context & Motivation
- `none/none` disables env override implicitly; expose explicit signals for tests/tools.

## Implementation Guidance
- In the explain dict, add `inspect_eval_disabled: bool` and `env_inspect_eval_model_raw`.
- Keep `env_inspect_eval_model` as effective value or `None`.

## Scope Definition
- Code: part of `resolve_model_explain(...)`.
- Tests: assert sentinel handling flags and raw/effective keys.

## Success Criteria
- Explicit, testable handling of the sentinel value.
