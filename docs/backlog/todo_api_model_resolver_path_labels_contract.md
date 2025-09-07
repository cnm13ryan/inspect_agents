# TODO: Model Resolver — Stabilize `path` Labels Contract

## Context & Motivation
- Debug `path` labels are currently implicit; decide whether to freeze them as public for tests/support tools.

## Implementation Guidance
- Export constants or document the label set; assert membership in a smoke test.

## Scope Definition
- Code/Docs: `src/inspect_agents/model.py`, docs note in environment reference.
- Tests: add a smoke test asserting label membership.

## Success Criteria
- Label contract documented; tests avoid brittle string comparisons.
