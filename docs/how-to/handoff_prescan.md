# Handoff Pre‑Scan (Executor) – Optional

Purpose: reduce scheduling overhead and make transcripts deterministic by enforcing “first handoff wins” before tools are scheduled.

Behavior (flagged):
- Enable with `INSPECT_EXECUTOR_PRESCAN_HANDOFF=1`.
- If the last assistant message contains any `transfer_to_*` handoff calls, the executor keeps only the first by order and filters out the rest (including any non‑handoff tools in that turn).
- For each filtered call, the executor emits a transcript `ToolEvent` with:
  - `error.type = "approval"`, `error.message = "Skipped due to handoff"`
  - `metadata.source = "executor/prescan"`
  - `metadata.selected_handoff_id` and `metadata.skipped_function`.

Precedence vs Approval Policy:
- When enabled, the executor runs before approval policies are applied, so approval policies will not see filtered calls.
- Operators can optionally mirror the approval event in the transcript by setting:
  - `INSPECT_EXECUTOR_PRESCAN_MIRROR_POLICY=1`
  - This adds a second `ToolEvent` per filtered call with `metadata.source = "policy/handoff_exclusive"` for parity with policy‑level enforcement.

Defaults:
- With the flag unset, behavior is unchanged; approval policies (e.g., `handoff_exclusive_policy`) enforce exclusivity at approval time and emit `policy/handoff_exclusive` events.

Notes:
- Pre‑scan never throws; all operations are best‑effort. If event emission fails, execution continues.

