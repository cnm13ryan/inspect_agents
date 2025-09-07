# TODO: Side‑Effect Helper — Approval‑Aware Fallback Policy

## Context & Motivation
- Fallbacks currently apply even when tool execution fails due to approval denial, potentially bypassing policy intent.

## Implementation Guidance
- Propagate minimal failure context from `execute_tools` (e.g., exception type/code).
- Skip fallbacks when the failure reason indicates approval denial; allow for timeouts/offline cases.

## Scope Definition
- Code: `src/inspect_agents/migration.py`.
- Tests: simulate approval denial and verify no Store mutation; allow fallback on simulated timeout.

## Success Criteria
- Policy‑aware behavior with tests covering deny vs timeout.
