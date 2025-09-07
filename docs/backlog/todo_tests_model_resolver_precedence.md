# TODO: Model Resolver — Precedence & Sentinel Env Tests

## Context & Motivation
- `resolve_model()` supports explicit model paths, role env mapping, global `INSPECT_EVAL_MODEL`, and provider defaults with required key checks.
- Add tests for edge cases and precedence, including the sentinel `INSPECT_EVAL_MODEL=none/none`.

## Implementation Guidance
- Code: `src/inspect_agents/model.py` (`resolve_model`, `_resolve_role_mapping`).
- Tests:
  - Explicit `model` with provider prefix wins.
  - Role env mapping overrides `INSPECT_EVAL_MODEL`.
  - `INSPECT_EVAL_MODEL=none/none` is ignored.
  - Remote providers without keys raise with exact env var names.
  - OpenAI‑compatible vendor path (`openai-api/<vendor>`) uses `<VENDOR>_API_KEY` and `<VENDOR>_MODEL`.

## Scope Definition
- Unit tests only; no functional change.

## Success Criteria
- Tests pass; failure messages are actionable and reference exact env var names.
