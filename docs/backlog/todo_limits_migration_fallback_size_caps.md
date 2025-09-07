# TODO: Side‑Effect Helper — Enforce Size Caps on Fallback Writes

## Context & Motivation
- Fallback writes currently bypass byte limits enforced by tool paths.

## Implementation Guidance
- Respect a conservative cap aligned with `INSPECT_AGENTS_FS_MAX_BYTES` or an explicit helper (e.g., `settings.max_tool_output_env`).
- Decide clip vs error on exceed; prefer error for files, clip for todos.

## Scope Definition
- Code: `src/inspect_agents/migration.py`.
- Tests: large content inputs produce expected behavior and logs.

## Success Criteria
- Consistent size enforcement across tool and fallback paths.

