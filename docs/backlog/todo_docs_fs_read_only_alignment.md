# TODO: Filesystem Read‑Only — Docs Alignment & Examples

Status: DONE (2025-09-10)
- Implemented: Expanded read‑only mode section with env exports, expected errors, and cross‑links.
- Docs: see docs/how-to/filesystem.md (Read‑Only Mode) and docs/reference/environment.md (flags and examples).

## Context & Motivation
- Read‑only mode is implemented for sandbox (`INSPECT_AGENTS_FS_READ_ONLY=1`).
- Improve docs to show a complete snippet (env exports, expected error string, and a minimal tool call) and cross‑link from environment reference, how‑to filesystem, and tools pages.

## Implementation Guidance
- Docs: update `docs/how-to/filesystem.md` (add explicit RO section), `docs/reference/environment.md` (expand description), and `docs/tools/*` where relevant.
- Add a short “expected error” example block for write/edit/delete in sandbox with the flag enabled.

## Scope Definition
- Docs only; no code changes.

## Success Criteria
- Docs updated; examples tested locally; cross‑links valid.
