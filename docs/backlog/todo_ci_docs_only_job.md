# TODO: CI — Add Docs‑Only Job (fast unit subset + link checker)

## Context & Motivation
- Docs‑only PRs currently run full workflows; a lighter job improves velocity.

## Implementation Guidance
- Detect docs‑only changes via path filters; run an offline unit subset (`-k iterative or tools or logging`) with `--maxfail=1` and a link checker.

## Scope Definition
- CI: `.github/workflows/*.yml` (new conditional job).

## Success Criteria
- Docs‑only PRs trigger the light job; others run full CI.
