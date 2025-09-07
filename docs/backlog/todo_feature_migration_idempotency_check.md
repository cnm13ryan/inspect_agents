# TODO: Side‑Effect Helper — Skip Fallback on Success (Idempotency)

## Context & Motivation
- Helper may double‑apply effects by running fallbacks after successful tool execution.

## Implementation Guidance
- Detect success by inspecting returned tool messages/results or a success flag.
- When success is detected for a function, do not apply its fallback.

## Scope Definition
- Code: `src/inspect_agents/migration.py`.
- Tests: cover both branches (success vs failure) with assertions on Store state.

## Success Criteria
- No double‑application; deterministic tests passing offline.
