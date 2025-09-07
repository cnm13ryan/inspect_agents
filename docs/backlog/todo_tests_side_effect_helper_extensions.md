# TODO: Tests — Side‑Effect Helper Edge Cases

## Context & Motivation
- Expand coverage for `_apply_side_effect_calls(...)` across edge cases to prevent regressions.

## Implementation Guidance
- Add tests for: unknown tools, malformed arguments, multiple assistant tool messages, approval denials vs timeouts, very large content, duplicate writes, handoff‑exclusive interactions, concurrent tool calls.

## Scope Definition
- Tests only; use offline stubs and Store assertions.

## Success Criteria
- Deterministic tests passing offline; documented gaps closed.

