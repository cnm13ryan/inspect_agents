# TODO: Deprecations — Gate Alias Warnings Behind `INSPECT_SHOW_DEPRECATIONS`

## Context & Motivation
- Underscore aliases remain silent; introduce opt‑in warnings to encourage migration without log noise.

## Implementation Guidance
- Implement `INSPECT_SHOW_DEPRECATIONS=1` gating for a one‑time `DeprecationWarning` on first alias access; plan to switch default next cycle.

## Scope Definition
- Code: alias definitions in `fs.py`, `filters.py` (and any similar).
- Docs: deprecation policy note.

## Success Criteria
- Opt‑in warnings available; documented migration path.
