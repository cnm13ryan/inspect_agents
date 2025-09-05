# TODO: read_file — Consistent Numbering (sandbox vs store)

## Context & Motivation
- `execute_read` formats numbered lines via `_format_lines(...)`.
- Store mode pads line numbers to width 6 (cat‑style). Sandbox path currently uses unpadded numbering in one branch.
- Docs promise padded cat‑style formatting. Make behavior consistent and adjust docs/tests.

## Implementation Guidance
- Code: `src/inspect_agents/tools_files.py`.
  - Ensure sandbox path uses the same padding as store (`pad=True`) or standardize to one convention; recommend padded for stable diffs.
  - Revisit the `pad=False` branch used after `sed` invocation.
- Docs: `docs/tools/read_file.md`, `docs/tools/typed_results.md` — confirm examples and wording.
- Tests: add coverage for both modes with the same expected numbering.

## Scope Definition
- Behavior change limited to formatting of line numbers.
- No change to truncation logic or limits.

## Success Criteria
- Consistent numbering across modes; docs updated; tests pass.

