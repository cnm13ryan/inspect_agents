# TODO: Iterative — Pruning/Truncation Behaviors

## Context & Motivation
- Iterative loop prunes by message count and uses a token‑aware per‑message truncation helper; also handles overflow hints.
- Add focused tests to prevent regressions in tail selection, orphan tool message drops, and overflow recovery.

## Implementation Guidance
- Code: `src/inspect_agents/iterative.py`, `src/inspect_agents/_conversation.py`, `src/inspect_agents/iterative_config.py`.
- Tests:
  - `_prune_history`: keeps first system + first user + tail window (`max_messages` vs `2*max_turns`).
  - Tool pairing: tool messages only retained if parent assistant call kept; salvage most recent pair when tail otherwise drops all tools.
  - Overflow path: on `IndexError`/`model_length`, hint appended, immediate prune, and continue.
  - Token‑cap path: when tokenizer present, per‑message truncation respects `per_msg_token_cap` and `truncate_last_k`.

## Scope Definition
- Unit/integration tests only; no functional changes.

## Success Criteria
- Tests pass; logs optionally show debug lines when `INSPECT_PRUNE_DEBUG` set.
