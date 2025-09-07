# TODO: tools.py — Migrate FS helpers to inspect_agents.fs

## Context & Motivation
- Remove duplication of `_fs_mode()` / `_use_sandbox_fs()` by delegating to `inspect_agents.fs` to keep behavior centralized.

## Implementation Guidance
- Replace local helpers in `src/inspect_agents/tools.py` with imports/aliases to `inspect_agents.fs.fs_mode` and `inspect_agents.fs.use_sandbox_fs`.
- Ensure no behavior changes to `standard_tools()` gating (only surface `text_editor()` when sandbox is active).

## Scope Definition
- Code: `src/inspect_agents/tools.py` only.
- Tests: reuse existing filesystem/sandbox tests; add a smoke test asserting identity with `fs.use_sandbox_fs`.

## Success Criteria
- No remaining local FS helpers in `tools.py`.
- `standard_tools()` continues to filter `bash_session` and gate `text_editor()` behind sandbox.

