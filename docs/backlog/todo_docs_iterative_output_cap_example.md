# TODO: Docs — Add `INSPECT_MAX_TOOL_OUTPUT` Example Invocation

Status: DONE (2025-09-10)
- Implemented: Added a concrete command example using `INSPECT_MAX_TOOL_OUTPUT=8192` in the Tool‑Output Truncation section.
- Docs: see docs/reference/iterative-agent-behavior.md (example block under Tool‑Output Truncation).

## Context & Motivation
- The reference mentions the env var but lacks a concrete command example.

## Implementation Guidance
- Add one example showing `INSPECT_MAX_TOOL_OUTPUT=8192` with a cautionary note about provider differences.

## Scope Definition
- Docs: `docs/reference/iterative-agent-behavior.md`.

## Success Criteria
- Example command present under Tool‑Output Truncation section.
