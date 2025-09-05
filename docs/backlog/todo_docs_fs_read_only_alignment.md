# TODO: Filesystem Read‑Only — Docs Alignment & Examples

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

