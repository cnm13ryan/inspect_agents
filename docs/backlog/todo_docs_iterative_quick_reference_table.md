# TODO: Docs — Add Iterative CLI Quick‑Reference Table

Status: DONE (2025-09-10)
- Implemented: Quick‑reference table for core flags added near the top of the iterative reference.
- Docs: see docs/reference/iterative-agent-behavior.md ("Quick Reference").

## Context & Motivation
- The reference is prose‑heavy; a compact flag table would improve scanning.

## Implementation Guidance
- Add a two‑column table (Flag → Description/Default) for core flags with a note that `--help` is the source of truth.

## Scope Definition
- Docs: `docs/reference/iterative-agent-behavior.md`.

## Success Criteria
- Table present near the top; avoids duplication drift with `--help`.
