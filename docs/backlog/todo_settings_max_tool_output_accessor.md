# TODO: Settings — Add `max_tool_output_env()` Accessor

Status: DONE (2025-09-10)
- Implemented: Added `settings.max_tool_output_env()` and adopted it in observability/iterative code paths.
- Code: src/inspect_agents/settings.py; used in src/inspect_agents/observability.py and src/inspect_agents/iterative.py.

## Context & Motivation
- Env parsing for `INSPECT_MAX_TOOL_OUTPUT` is duplicated in observability/iterative.

## Implementation Guidance
- Implement `settings.max_tool_output_env() -> int | None` (non‑negative ints; 0 allowed; None when unset/invalid) and adopt it in both call sites without changing precedence.

## Scope Definition
- Code: `src/inspect_agents/settings.py`, `observability.py`, `iterative.py`.
- Tests: ensure existing truncation tests remain green.

## Success Criteria
- Single accessor used across code; behavior unchanged.
