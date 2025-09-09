# TODO: Docs/Release — Add CHANGELOG and Release Notes Automation

## Context & Motivation
- Provide user‑facing release notes with clear upgrade guidance.
- Establish a predictable audit trail (versions → changes) for support/compliance.
- Reduce PR/release friction by standardizing categories and automating notes.

## Implementation Guidance
- Add `CHANGELOG.md` following “Keep a Changelog” with SemVer sections:
  - `## [Unreleased]` with sub‑sections: Added | Changed | Deprecated | Removed | Fixed | Security.
  - `## [vX.Y.Z] – YYYY‑MM‑DD` entries for future releases.
- Add Release Drafter configuration:
  - File: `.github/release-drafter.yml` with categories mapped from labels
    (e.g., `type:feat` → Added, `type:fix` → Fixed, `type:perf` → Changed,
    `breaking` badge → highlight in a “Breaking Changes” section).
  - Optional: change grouping to align with Conventional Commits if preferred.
- Add GitHub Action workflow:
  - File: `.github/workflows/release-drafter.yml` to update the draft release on
    pushes to `inspect-ai-rewrite` (or default) and on PR open/merge/label.
- PR template alignment (optional, low effort):
  - Extend `.github/pull_request_template.md` with a small “Changelog category”
    checklist and “Breaking change?” checkbox to encourage proper labels.
- Contributing docs (optional):
  - Add a short note in `CONTRIBUTING.md` on labeling PRs and drafting release
    notes; clarify that Release Drafter composes notes automatically.

## Scope Definition
- Docs + GitHub configuration only; no runtime code changes.
- No mandate to manually edit `CHANGELOG.md` per PR; rely on labels → Release
  Drafter for aggregation. `CHANGELOG.md` is maintained at release cut time.
- Labels expected (or similar): `type:feat`, `type:fix`, `type:perf`, `type:docs`,
  `type:refactor`, `type:chore`, `type:ci`, plus `breaking` when applicable.

## Success Criteria
- `CHANGELOG.md` present with an `Unreleased` section scaffold.
- Draft releases auto‑populate with categorized changes after labeled PR merges.
- First tagged release (e.g., `v0.1.0`) mirrors the draft content in both
  GitHub Releases and `CHANGELOG.md`.
- PR authors consistently apply labels or select a changelog category via the
  PR template.

## Rollout Plan
1) Land `CHANGELOG.md`, `.github/release-drafter.yml`, and workflow on base branch.
2) Validate the Action on a merged labeled PR (non‑production change).
3) Cut `v0.1.0` and sync `CHANGELOG.md` from the draft release.
