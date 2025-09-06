# TODO: run_agent — Mutable Default for `limits`

Status: DONE (2025-09-06)
- Implemented: `run_agent(..., limits: list[Any] | None = None)` with in-function normalization to a new list when `None`.
  - Code: `src/inspect_agents/run.py` (signature updated; defensive normalization added near top).

## Context & Motivation
- `run_agent(..., limits: list[Any] = [])` uses a mutable default list.
- Mutable defaults can leak state across calls and surprise users/tests.
- Fixing this removes a subtle source of flakiness.

## Implementation Guidance
- File: `src/inspect_agents/run.py`.
- Change signature to `limits: list[Any] | None = None`.
- In function body: `limits = [] if limits is None else limits` before use.
- Audit call sites (if any) for passing `limits` positionally.

## Scope Definition
- Pure refactor; no behavior change intended beyond removing shared state.
- Add a small unit test ensuring repeated calls with default don’t accumulate limits.

## Success Criteria
- Code updated as above.
- Tests: new test passes; no regressions.
