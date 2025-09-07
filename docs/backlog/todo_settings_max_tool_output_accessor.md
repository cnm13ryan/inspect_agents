# TODO: Settings — Add `max_tool_output_env()` Accessor

## Context & Motivation
- Env parsing for `INSPECT_MAX_TOOL_OUTPUT` is duplicated in observability/iterative.

## Implementation Guidance
- Implement `settings.max_tool_output_env() -> int | None` (non‑negative ints; 0 allowed; None when unset/invalid) and adopt it in both call sites without changing precedence.

## Scope Definition
- Code: `src/inspect_agents/settings.py`, `observability.py`, `iterative.py`.
- Tests: ensure existing truncation tests remain green.

## Success Criteria
- Single accessor used across code; behavior unchanged.
