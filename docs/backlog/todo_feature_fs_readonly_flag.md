# TODO: Filesystem Sandbox — Enforce Read‑Only Mode Flag

Status: DONE (2025-09-05)
- Implemented: `INSPECT_AGENTS_FS_READ_ONLY` blocks write/edit/delete in sandbox mode and emits `tool_event` with `phase="error"` and `error="SandboxReadOnly"`.
  - Code: `src/inspect_agents/tools_files.py` (guards in `execute_write`, `execute_edit`, and `execute_delete`).
  - Docs: mention present in `docs/how-to/filesystem.md` and `docs/reference/environment.md`; see follow‑up "Docs" below for expansion/examples.

## Context & Motivation
- Purpose: provide a sandbox read‑only mode that blocks writes/edits/deletes to host FS.
- Problem: sandbox currently allows write/edit (delete disabled) with no repo‑wide read‑only switch.
- Value: safer demos/prod where the host filesystem must not be mutated.
- Constraints: only affect sandbox mode; store mode semantics unchanged.

## Implementation Notes (as built)
- Guard checks appear at the top of write/edit/delete paths and short‑circuit before calling editor/bash stubs.
- Delete remains unsupported in sandbox regardless of the flag; read‑only adds a specific error for visibility.

## Scope Definition
- Tests: add coverage for write/edit/delete under `INSPECT_AGENTS_FS_MODE=sandbox` + read‑only flag; assert exception type/message and absence of editor/bash calls.
- Docs: expand examples with expected error payload and flags snippet.

## Success Criteria
- Behavior: sandbox write/edit/delete are blocked when env flag is set; delete remains blocked even without flag (status quo).
- Tests: new tests pass; existing FS tests remain green.
- Docs: ADR 0004/how‑to/env reference include the flag and examples.
