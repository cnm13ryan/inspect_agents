# TODO: Observability — Effective Tool‑Output Limit (precedence + log‑once)

## Context & Motivation
- The one‑time observability log for the effective tool‑output limit helps operators debug truncation.
- Need tests to lock in precedence (explicit param > GenerateConfig > env > default) and “log once” behavior across multiple tool calls.

## Implementation Guidance
- Code: `src/inspect_agents/observability.py` (`maybe_emit_effective_tool_output_limit_log`) and `src/inspect_agents/tools.py` (flag `_EFFECTIVE_LIMIT_LOGGED`).
- Tests:
  - Param precedence: set active GenerateConfig with and without `max_tool_output`, then set `INSPECT_MAX_TOOL_OUTPUT` and assert the effective limit.
  - Log‑once: simulate two tool events and assert a single observability log line.
  - Env parsing: negative/empty values ignored.

## Scope Definition
- Unit tests only; no functional changes.

## Success Criteria
- Tests cover precedence and log‑once; CI green.
