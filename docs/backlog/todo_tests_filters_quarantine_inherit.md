# TODO: Filters — Cascade/Inheritance + Scoped Summary Caps

## Context & Motivation
- `default_input_filter` supports per‑agent env overrides, inheritance via store, and global defaults; scoped summaries have size caps via env.
- Tests should lock intended precedence and ensure summaries respect byte/todo/file caps.

## Implementation Guidance
- Code: `src/inspect_agents/filters.py`.
- Tests:
  - Per‑agent env (`INSPECT_QUARANTINE_MODE__<name>`) overrides all.
  - When inheritance is enabled (`INSPECT_QUARANTINE_INHERIT=1`), nested handoffs inherit the recorded active filter.
  - Scoped summary obeys `INSPECT_SCOPED_MAX_BYTES`, `INSPECT_SCOPED_MAX_TODOS`, `INSPECT_SCOPED_MAX_FILES`; logs size trimming when needed.

## Scope Definition
- Unit tests; no behavior change.

## Success Criteria
- Tests pass; coverage for precedence and summary sizing.
