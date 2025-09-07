# TODO: Side‑Effect Helper — Add Debug Logs and Tests

## Context & Motivation
- `_apply_side_effect_calls(...)` swallows exceptions without logging, obscuring failures and fallbacks.

## Implementation Guidance
- Add a module logger `inspect_agents.migration` and emit `DEBUG` logs when:
  - `execute_tools` fails, and
  - fallbacks apply (`write_file`/`write_todos`).
- Include fields: `reason`, `tool_functions`, and `fallback_applied`.

## Scope Definition
- Code: `src/inspect_agents/migration.py`.
- Tests: new unit test asserting a debug log is emitted on replay failure and on fallback.

## Success Criteria
- Deterministic tests passing offline; no change to user‑visible behavior.

