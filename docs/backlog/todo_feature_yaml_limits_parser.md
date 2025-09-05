# TODO: YAML Limits — Parse and Return Inspect Limits

Status: DONE (2025-09-05)
- Implemented in `src/inspect_agents/config.py` via `parse_limits()` and `_limit_from_dict()`; values are returned from `build_from_config`/`load_and_build` and can be passed to `run_agent(..., limits=limits)`.
- Follow‑ups below track docs/examples alignment and additional tests.

## Context & Motivation
- Purpose: make YAML `limits` actionable by returning Inspect `Limit` objects from the config path.
- Problem: YAML field exists but is ignored; `run_agent` already accepts `limits`.
- Value: first‑class control of time/message/token caps from config.

## Implementation Notes (as built)
- Code: `src/inspect_agents/config.py` implements `_limit_from_dict()` supporting a minimal typed schema of the form `{type: "time|message|token", value: <number>}` with common aliases like `seconds`, `max`, and `limit`. See also `parse_limits()` and its use in `build_from_config()`.
- Runner: `src/inspect_agents/run.py` accepts `limits` and forwards them to Inspect’s engine.
- Difference from earlier proposal: we chose an explicit `type` key to avoid ambiguous short forms; aliases are still accepted for ergonomics.

## Scope Definition
- Keep the typed `type/value` schema with documented aliases.
- Preserve backward compatibility (empty input → `[]`; invalid entries raise a clear `ValueError`).
- Add tests around bad shapes and alias handling.

## Success Criteria
- Behavior: runs end on configured limits with expected error classes.
- Tests: unit tests cover type parsing, alias handling, and error messages.
- Docs: examples in guides/index/reference match the implemented schema.
