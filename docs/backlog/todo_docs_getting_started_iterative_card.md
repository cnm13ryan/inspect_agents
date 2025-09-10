# TODO: Docs — Add Iterative Quick‑Start Card to Getting Started

Status: DONE (2025-09-10)
- Implemented: Added a minimal iterative runner snippet (300s/20 steps) to the Quickstart and linked back to the reference.
- Docs: see docs/getting-started/inspect_agents_quickstart.md.

## Context & Motivation
- Getting Started lacks a minimal iterative snippet; examples link to reference only.

## Implementation Guidance
- Add a 3–4 line example with `uv run python examples/runners/iterative_runner.py --time-limit 300 --max-steps 20 "..."` and link to the reference.

## Scope Definition
- Docs: `docs/getting-started/inspect_agents_quickstart.md`.

## Success Criteria
- Card present; no duplicated flag tables; link back to the reference page.
