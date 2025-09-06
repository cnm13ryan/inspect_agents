# TODO: delete (sandbox) — Unify Error Code/Message with Docs

Status: DONE (2025-09-06)
- Implemented: sandbox delete raises canonical `ToolException("SandboxUnsupported")`; wrapper maps to descriptive message for higher‑level calls while preserving the canonical code in logs.
  - Code: `src/inspect_agents/tools_files.py` (`execute_delete` raises `SandboxUnsupported`; factory wrapper turns it into a user‑facing message).
  - Docs: `docs/how-to/filesystem.md` Delete Policy reflects canonical string and guidance to switch to store mode.

## Context & Motivation
- In sandbox mode, `delete` is intentionally unsupported. Current code raises `ToolException` with message explaining sandbox is disabled and logs `SandboxUnsupported`.
- Docs/pages mention a slightly different phrasing. Align the canonical error string and documentation.

## Implementation Guidance
- Code: `src/inspect_agents/tools_files.py` → `execute_delete`.
  - Choose canonical: keep `SandboxUnsupported` as error code in logs and `ToolException("SandboxUnsupported")` or map to a stable message used in docs.
- Docs: `docs/tools/delete_file.md`, `docs/tools/files.md`, and `docs/how-to/filesystem.md` — ensure message and behavior match exactly; add a short example with the error.

## Scope Definition
- No functional change; unify phrasing and log/error code names.
- Add a tiny test asserting the raised message and the logger payload.

## Success Criteria
- Canonical error string/code established and used across code/docs.
- Tests pass; docs updated.
