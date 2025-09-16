# Open Questions — Design Discussion

Status: living document. Last updated: 2025-09-04.

This page records design questions that need product/engineering decisions. Items include context, current behavior, options, trade‑offs, and proposed next steps. PRs should link the relevant section when introducing behavior that touches these topics.

## Filesystem/Sandbox — Consolidation of Utilities

Context
- We introduced `src/inspect_agents/fs.py` to unify filesystem configuration and sandbox helpers that were duplicated across `tools_files.py` and `tools.py`.
- Goals: single source of truth for mode/root/limits/timeouts parsing, sandbox preflight with TTL cache, symlink denial, and root confinement checks; minimize import coupling and avoid cycles.
- Constraint: preserve behavior, exception text, and log payloads; keep wrapper tools’ external behavior unchanged.

Current State
- New module `inspect_agents.fs` exists and is dependency‑light (stdlib, anyio, optional upstream exception type). Callers can adopt it incrementally via compatibility aliases (`_default_tool_timeout`, `_ensure_sandbox_ready`, etc.).
- `tools_files.py` now imports `fs` and overrides local helper bindings to route through the consolidated implementations while leaving the original helper bodies in place for now (risk‑free delegation). Follow‑up cleanup is pending.

### Q1 — Exceptions Source

Question
- Should `fs.py` import `ToolException` from `inspect_agents.exceptions` to guarantee a single exception type across modules?

Background
- Some tests and callers assert on `ToolException.message` or rely on consistent exception class identity. Today `fs.py` prefers the upstream type, with a local fallback, while other modules import from `inspect_agents.exceptions`.

Options
- A) Import from `inspect_agents.exceptions` inside `fs.py` and drop the local fallback. Ensures uniform type but adds a local dependency.
- B) Keep current approach (prefer upstream with fallback), and require callers to normalize at boundaries. Fewer intra‑repo deps; risk of mixed types.

Trade‑offs
- A avoids type fragmentation; a minor risk of cycles if `exceptions` later imports `fs`. B keeps `fs` more standalone but may complicate assertions.

Proposed Direction
- Prefer A (centralized exceptions). Verify no import cycle by keeping `exceptions` minimal and never importing `fs` from there.

Decision Needed
- Approve switching `fs.py` to `from inspect_agents.exceptions import ToolException`.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: `fs.py` imports `ToolException` from the centralized exceptions module, ensuring a single exception type across modules.
**Evidence**: See `src/inspect_agents/fs.py` (imports `from .exceptions import ToolException`). 【F:src/inspect_agents/fs.py- L22-L24】
**Conclusion**: Option A is implemented (centralized exceptions). This item can be marked resolved.

</details>

### Q2 — Logging Path for Preflight Warnings

Question
- Should `ensure_sandbox_ready()` log via `observability.log_tool_event(...)` to match existing payloads exactly, or keep the lightweight JSON logger in `fs.py`?

Background
- `tools_files.py` used `_log_tool_event` for `files:sandbox_preflight` warnings. `fs.py` currently emits an equivalent JSON payload directly to avoid importing local modules (cycle risk).

Options
- A) Route logging through `observability.log_tool_event` for perfect parity.
- B) Keep in‑module JSON logging with identical fields; rely on shared log ingestion.

Trade‑offs
- A guarantees identical formatting/filters but introduces a dependency edge. B keeps `fs` cycle‑free and simple; low risk if payload matches.

Proposed Direction
- Start with B (current). If observability requires central hooks (sampling, redaction), we can inject a logger callback from callers to avoid direct imports.

Decision Needed
- Confirm whether parity via observability hook is required now.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: `ensure_sandbox_ready()` logs a structured JSON payload via the module logger (not `observability.log_tool_event`).
**Evidence**: `src/inspect_agents/fs.py` — in the preflight failure path, emits `logger.info("tool_event %s", json.dumps(payload, ...))` with fields `{tool:"files:sandbox_preflight", phase:"warn", ok:false, ...}`. 【F:src/inspect_agents/fs.py- L317-L323】
**Conclusion**: Option B is in effect (local JSON logging with identical fields). No parity hook is used.

</details>

### Q3 — Public vs Underscore API Names

Question
- Do we keep both public (`truthy`, `fs_root`, `max_bytes`, ...) and underscore aliases (`_truthy`, `_fs_root`, `_max_bytes`, ...) or deprecate underscores?

Background
- Underscore names exist to minimize churn during migration. Long‑term, we want a clean public API.

Options
- A) Keep both until all callers migrate; then remove underscore forms with a deprecation window.
- B) Immediately switch all callers to public names and drop underscores.

Trade‑offs
- A enables incremental adoption with low risk. B reduces API surface faster but increases migration blast radius.

Proposed Direction
- A with a short deprecation plan (announce in release notes; remove underscore aliases after two minor versions).

Decision Needed
- Approve deprecation timeline for underscore aliases.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Public helpers exist alongside underscore aliases for back‑compat.
**Evidence**: `src/inspect_agents/fs.py` exports both public helpers and underscore alias names (e.g., `_truthy = truthy`, `_fs_mode = fs_mode`, `_use_sandbox_fs = use_sandbox_fs`).
**Conclusion**: Option A (keep both) is implemented. A formal deprecation timeline is not yet encoded in code/docs (timeline decision remains optional).

</details>

⚠️ Still Open - Requires Decision
- Formalize and document the deprecation timeline for underscore
  aliases (e.g., announce now; remove after two minor versions). No
  user-visible policy exists yet.

### Q4 — Duplicate Code Cleanup in `tools_files.py`

Question
- When should we remove the local helper implementations now shadowed by `fs` aliases?

Background
- `tools_files.py` currently overrides local helpers with `fs` bindings to ensure centralized behavior without removing code blocks yet.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: `tools_files.py` now directly binds to `inspect_agents.fs` helpers and no longer carries duplicate local implementations of those helpers.
**Evidence**: `src/inspect_agents/tools_files.py` adopts `fs` helpers via assignments (e.g., `reset_sandbox_preflight_cache = _fs.reset_sandbox_preflight_cache`, `_ensure_sandbox_ready = _fs.ensure_sandbox_ready`, etc.).
**Conclusion**: Option A (delete shadowed helper bodies / keep only aliases) is effectively complete.

</details>

Options
- A) Delete shadowed helper bodies now (small, targeted diff) and keep only the alias assignments.
- B) Keep bodies for one release as a rollback safety, with a comment pointing to `fs`.

Trade‑offs
- A reduces duplication immediately and prevents drift. B gives a safety net if we need to revert quickly.

Proposed Direction
- A (clean up now) given version control provides rollback; add a brief migration note in the PR.

Decision Needed
- Approve immediate removal of shadowed helpers.

### Q5 — `tools.py` Migration to `fs`

Question
- Should we switch `tools.py` helpers (`_truthy`, `_use_sandbox_fs`, `_default_tool_timeout`) to import from `fs` in the same refactor or as a follow‑up?

Background
- `tools.py` duplicates some FS helpers. Changing it is low risk but touches another module’s behavior.

Options
- A) Update `tools.py` now to import from `fs`.
- B) Follow‑up change with its own tests/validation.

Trade‑offs
- A reduces duplication immediately; slightly larger PR surface. B reduces change scope today but prolongs duplication.

Proposed Direction
- A, kept surgical (import + remove duplicates) and validated by existing tool behavior tests.

Decision Needed
- Approve migration of `tools.py` to `fs` helpers.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: `tools.py` now delegates filesystem mode helpers to the unified `fs` module.
**Evidence**: `src/inspect_agents/tools.py` imports `fs` and aliases its helpers: `_fs_mode = _fs.fs_mode` and `_use_sandbox_fs = _fs.use_sandbox_fs` (L102–L104). 【F:src/inspect_agents/tools.py‑ L102-L104】
**Conclusion**: Option A implemented — duplication removed by delegating to `fs` within `tools.py`.

</details>

### Q6 — Unit Tests for `fs.py`

Question
- Should we add dedicated tests for `fs.py` (preflight TTL, `skip/force` modes, root confinement, symlink denial) now or after full migration?

Background
- Current tests exercise behavior via tools; targeted `fs` tests would improve signal and guard regressions.

Options
- A) Add focused tests now under `tests/inspect_agents/` with environment‑driven branches.
- B) Defer until callers fully adopt `fs` to avoid churn in expectations.

Trade‑offs
- A increases confidence immediately; minimal maintenance cost. B keeps this PR smaller but leaves a coverage gap.

Proposed Direction
- A. Keep tests deterministic (`NO_NETWORK=1`), stub tool modules for sandbox stubs, and assert log payloads/exception messages.

Decision Needed
- Approve adding an `fs` test module in the next change.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Dedicated unit tests for `fs` behavior exist (preflight `skip/force/auto` + TTL, logging context).
**Evidence**: `tests/unit/inspect_agents/fs/test_sandbox_preflight_modes.py` exercises `_ensure_sandbox_ready` and `reset_sandbox_preflight_cache()` across modes with log assertions.
**Conclusion**: Tests are already in place; this item can be marked complete.

</details>

### Q7 — Documentation Updates

Question
- Should we update docs to point to `inspect_agents.fs` as the canonical source for FS behavior and environment knobs?

Background
- Existing docs reference behavior spread across multiple modules. Centralizing improves discoverability.

Options
- A) Update references in How‑To/Reference pages to link to this consolidation and the env variables.
- B) Keep current docs and update later post‑migration.

Trade‑offs
- A reduces confusion immediately; small doc changes. B risks stale guidance.

Proposed Direction
- A. Add a short “Design Note” in Filesystem How‑To and Reference pages linking to this section.

<details>
<summary>✅ Answer Found in Implementation (Docs Updated)</summary>

**Finding**: Filesystem behavior and knobs are documented in How‑To and Reference pages, including sandbox routing, preflight, delete policy, and read‑only mode.
**Evidence**: `docs/how-to/filesystem.md` (Routing, Preflight, Delete Policy, Size/Timeouts); `docs/reference/environment.md` (FS env flags, including `INSPECT_AGENTS_FS_READ_ONLY`).
**Conclusion**: Documentation reflects the consolidated FS design. A brief cross‑link/“Design Note” back to this section can be added later but is not a blocker.

</details>

Decision Needed
- Approve doc updates in the next doc PR.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Added a short “Design Note” backlink in the Filesystem How‑To pointing back to this design page.
**Evidence**: `docs/how-to/filesystem.md` includes a note linking to Design → Open Questions above “See Also”. 【F:docs/how-to/filesystem.md‑ L119-L123】
**Conclusion**: Cross-link present; documentation update complete.

</details>

---

## Filesystem Sandbox — Read‑only Mode (new)

Context
- We plan a read‑only mode in sandbox (`INSPECT_AGENTS_FS_READ_ONLY=1`) where write/edit/delete are blocked while listing and reading remain allowed. This is referenced from the Environment reference.

Open Points
- Error taxonomy and message text (`ToolException("SandboxReadOnly")` vs richer message).
- Observability payload shape (include `mode`, `fs_root`, and attempted operation?).
- Interaction with preflight `force` mode and typed result toggles.

Next Steps
- Finalize error/message contract and add tests covering ls/read allowed and write/edit/delete denied with correct logs/fields.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Read‑only behavior is implemented behind `INSPECT_AGENTS_FS_READ_ONLY=1` for sandbox mode. Write/edit/delete return a `ToolException("SandboxReadOnly")` and emit `tool_event` with `error: "SandboxReadOnly"`; ls/read remain allowed.
**Evidence**: `src/inspect_agents/tools_files.py` (read‑only guards): write guard for `files:write` and `SandboxReadOnly` error 【F:src/inspect_agents/tools_files.py- L801-L808】; edit guard for `files:edit` 【F:src/inspect_agents/tools_files.py- L960-L966】; delete guard for `files:delete` 【F:src/inspect_agents/tools_files.py- L1316-L1323】. Tests assert exception text and `tool_event` payloads for write/edit/delete. 【F:tests/unit/inspect_agents/fs/test_fs_sandbox_readonly.py- L15-L28】【F:tests/unit/inspect_agents/fs/test_fs_sandbox_readonly.py- L30-L44】【F:tests/unit/inspect_agents/fs/test_fs_sandbox_readonly.py- L46-L62】
**Conclusion**: The chosen taxonomy/message and observability shape are implemented and tested.

</details>

#
# Open Questions — Side‑Effect Tool Application Helper (Migration)

Context
- We extracted the inline logic in `create_deep_agent` that applies side‑effecting tool calls when a `submit` appears in the same turn. The new helper `_apply_side_effect_calls(messages, tools)` locates the latest assistant message with tool calls, excludes `submit`, replays via `execute_tools`, and then applies defensive Store fallbacks for `write_file` and `write_todos`. The behavior and signature of `create_deep_agent` remain unchanged.

Current State
- Helper lives in `src/inspect_agents/migration.py` and is invoked immediately after the base ReAct agent returns messages.
- Fallback mirrors only `write_file` and `write_todos`; other tools are not mirrored.
- Exceptions are swallowed to preserve best‑effort semantics identical to pre‑extraction logic.

Why it matters
- Extracting this logic enables unit testing and safer maintenance of the migration shim, but raises policy and API questions (visibility, scope of fallbacks, approvals, and typing) that should be decided explicitly.

### Q1 — Helper Visibility (private vs. exported)

Question
- Should `_apply_side_effect_calls` remain private or be exported in `__all__` and documented as part of the migration surface?

Options
- Private (status quo): minimal public surface; tests can still import it directly but risk churn.
- Exported: stable for external reuse; increases long‑term API commitment.

Recommendation
- Keep private for now; promote to public if external adoption emerges.

Acceptance Criteria
- Decide visibility and reflect it in `__all__`, docs, and tests.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: `_apply_side_effect_calls` remains private; only `create_deep_agent` is exported.
**Evidence**: `src/inspect_agents/migration.py` defines `_apply_side_effect_calls(...)`; `__all__ = ["create_deep_agent"]`.
**Conclusion**: Private visibility chosen (status quo).

</details>

### Q2 — Helper Location (module placement)

Question
- Keep the helper in `migration.py` or move to a dedicated `migration_utils.py` (or `migration/_side_effects.py`)?

Trade‑offs
- Collocation improves discoverability and keeps related logic together; a separate module clarifies reuse and keeps the file smaller.

Recommendation
- Keep in `migration.py` until an additional caller appears; then extract.

Acceptance Criteria
- Confirm location; if moved, update imports and docs.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: The helper remains in `migration.py`.
**Evidence**: `src/inspect_agents/migration.py` contains the helper and its caller; no separate module exists.
**Conclusion**: Keep-in-place option selected.

</details>

### Q3 — Fallback Scope (which tools to mirror)

Question
- Should the fallback include more side‑effect tools (e.g., `update_todo_status`, file edits) beyond `write_file` and `write_todos`?

Trade‑offs
- Expanding increases resilience when `execute_tools` is skipped, but risks duplicating tool logic and widening blast radius.

Recommendation
- Keep minimal scope; add new cases only with concrete requirements and tests.

Acceptance Criteria
- Enumerate tools to mirror, add tests, and document rationale.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Fallback mirrors only `write_file` and `write_todos` side‑effects.
**Evidence**: `src/inspect_agents/migration.py` fallback branch updates `Files.put_file(...)` and `Todos.set_todos(...)`; no other tools are mirrored.
**Conclusion**: Minimal scope retained (as recommended).

</details>

### Q4 — API Shape and Typing

Question
- Should the helper be strictly typed (e.g., `list[ChatMessage]`, `Sequence[Tool|ToolDef|ToolSource]`) instead of `list[Any]` / `Sequence[object]`?

Trade‑offs
- Stronger typing aids tooling but may introduce tighter coupling or import cycles.

Recommendation
- Keep dynamic typing until the API stabilizes; revisit later.

Acceptance Criteria
- Decide typing strictness; if tightened, update annotations and add type‑focused tests.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Dynamic typing is used (`list[Any]`, `Sequence[object]`); no strict typed API introduced.
**Evidence**: `src/inspect_agents/migration.py` signatures for the helper and builder.
**Conclusion**: Keep dynamic typing (status quo).

</details>

### Q5 — Error Reporting and Observability

Question
- The helper swallows exceptions. Should it emit debug‑level logs (e.g., when replay fails or fallback applies)?

Recommendation
- Add low‑noise debug logs under an `inspect_agents.migration` logger, preserving user‑visible behavior.

Acceptance Criteria
- Define log fields/levels; add a test asserting a log entry in failure/fallback paths.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Low‑noise debug logs are emitted for execute path selection/failure and fallback application.
**Evidence**: `src/inspect_agents/migration.py` logs `side_effects.execute_tools_invoked/failed` and `side_effects.fallback_begin/done`. 【F:src/inspect_agents/migration.py‑ L24-L27】【F:src/inspect_agents/migration.py‑ L47-L60】【F:src/inspect_agents/migration.py‑ L66-L87】 Unit test asserts fallback logs via caplog. 【F:tests/unit/inspect_agents/migration/test_side_effect_helper_logging.py‑ L1-L27】【F:tests/unit/inspect_agents/migration/test_side_effect_helper_logging.py‑ L29-L45】
**Conclusion**: Debug observability added without changing behavior; logs are under `inspect_agents.migration` at DEBUG level.

</details>

### Q6 — Approvals and Policy Interplay

Question
- If `execute_tools` fails due to approval denial, should the fallback still apply (potentially bypassing the approval intent)?

Options
- Always fallback (status quo).
- Policy‑aware fallback: skip fallback on approval denials; only apply on timeouts/offline conditions.

Recommendation
- Make fallback policy‑aware when approvals are active; propagate minimal failure context from `execute_tools` to the helper to decide.

Acceptance Criteria
- Specify allowed fallback conditions; add tests simulating approval denials to ensure no Store mutation occurs.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Fallbacks are now policy‑aware: when `execute_tools` fails due to approval denial, fallbacks are skipped.
**Evidence**: `src/inspect_agents/migration.py` detects denial via `exc.type` or message keywords and logs `side_effects.approval_denied; skipping_fallback=true`. 【F:src/inspect_agents/migration.py‑ L66-L74】【F:src/inspect_agents/migration.py‑ L76-L86】 Unit test stubs `execute_tools` to raise an approval‑denied error and asserts no fallback writes occurred and the log marker is present. 【F:tests/unit/inspect_agents/migration/test_policy_aware_fallback.py‑ L1-L20】【F:tests/unit/inspect_agents/migration/test_policy_aware_fallback.py‑ L22-L46】
**Conclusion**: Approval‑aware behavior implemented with low‑noise logging.

</details>

### Q7 — Idempotency and Double‑Application

Question
- The helper runs `execute_tools` and then attempts fallbacks; this can double‑apply effects.

Recommendation
- If `execute_tools` returns tool messages (or transcript shows success), skip fallbacks.

Acceptance Criteria
- Implement a success check and add tests to cover both branches.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: The helper now inspects Store state after `execute_tools` and only applies fallbacks for calls still pending.
**Evidence**: `src/inspect_agents/migration.py` computes a `pending` list by checking `Files.get_file(path)==content` for `write_file` and equality of `(content,status)` pairs for `write_todos`; only `pending` are applied. Logs include `fallback_begin count=<pending>` and `fallback_done wrote_files=... wrote_todos=...`. Test `test_execute_tools_success_skips_fallback` stubs `execute_tools` to apply changes and asserts `wrote_files=0 wrote_todos=0`. 【F:src/inspect_agents/migration.py‑ L90-L118】【F:src/inspect_agents/migration.py‑ L119-L138】【F:tests/unit/inspect_agents/migration/test_side_effect_helper_logging.py‑ L47-L88】
**Conclusion**: Idempotency is addressed; fallbacks are skipped when side effects are already applied.

</details>

### Q8 — Instance Scoping for Store Models

Question
- Should the fallback accept an optional `instance` and pass it to `store_as(...)` to isolate per‑agent state?

Trade‑offs
- Default instance preserves back‑compat; explicit instance improves isolation but requires plumbing through the call path.

Recommendation
- Keep default instance now; consider parameterization if multi‑agent isolation is needed.

Acceptance Criteria
- Decide scoping; if parameterized, update callers and tests.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Migration fallback accepts an optional `instance` and writes to `Files`/`Todos` for that instance when provided.
**Evidence**: `_apply_side_effect_calls(..., instance=...)` passes the instance to `store_as(Files|Todos, instance=...)` when inspecting/applying fallbacks. 【F:src/inspect_agents/migration.py‑ L100-L116】【F:src/inspect_agents/migration.py‑ L162-L171】【F:src/inspect_agents/migration.py‑ L187-L197】 Unit test asserts writes appear under the specified instance and not under the default. 【F:tests/unit/inspect_agents/migration/test_instance_scoping.py‑ L1-L20】【F:tests/unit/inspect_agents/migration/test_instance_scoping.py‑ L22-L40】
**Conclusion**: Instance scoping supported (optional); default remains unchanged for back‑compat.

</details>

### Q9 — Limits and Large Content

Question
- Should fallback writes enforce size limits comparable to tool‑path output limits?

Recommendation
- Respect a conservative cap (aligned with existing limits) in fallback to avoid unbounded Store writes.

Acceptance Criteria
- Define the limit and behavior on exceed (clip vs. error); add tests.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Fallback writes now enforce a byte ceiling consistent with tool paths; oversize writes are skipped with a DEBUG log.
**Evidence**: `src/inspect_agents/migration.py` checks `len(content.encode('utf-8')) > fs.max_bytes()` and logs `side_effects.fallback_file_too_large` instead of writing. 【F:src/inspect_agents/migration.py‑ L96-L108】 Unit test asserts guard and absence of the file when over the limit. 【F:tests/unit/inspect_agents/migration/test_fallback_size_limit.py‑ L1-L20】【F:tests/unit/inspect_agents/migration/test_fallback_size_limit.py‑ L22-L46】
**Conclusion**: Limits parity achieved for fallback writes with low‑noise observability.

</details>

### Q10 — Test Coverage Extensions

Gaps / Candidates
- Unknown tools, malformed arguments, multiple assistant tool messages, approval denials, very large content, duplicate writes, handoff‑exclusive interactions, concurrent tool calls.

Acceptance Criteria
- Prioritize and add targeted tests; keep deterministic/offline by default.

⚠️ Still Open - Requires Decision
- Prioritize which remaining scenarios to add first (unknown tools,
  malformed args, concurrent calls, handoff-exclusive). No additional
  tests landed yet beyond those cited above.

---

## Iterative Agent Docs & CLI — Open Questions (new)

### Q1 — Supervisor Flags Coverage

Question
- Should we document `examples/runners/supervisor_runner.py` flags alongside the Iterative Agent reference, or keep supervisor content separate?

Background
- The Iterative Agent reference now includes CLI usage for `examples/runners/iterative_runner.py`, `profiled_runner.py`, and the Inspect task. The supervisor demo (`examples/runners/supervisor_runner.py`) exposes provider/model and standard tool toggles but is not covered in that page.

Options
- A) Add a short “Supervisor Runner” subsection under the Iterative Agent reference’s CLI section.
- B) Create a separate Supervisor reference and link both directions.

Trade‑offs
- A improves discoverability with minimal sprawl but mixes concerns; B keeps conceptual boundaries clear but adds another page to maintain.

Proposed Direction
- A. Add a compact subsection now; revisit a dedicated Supervisor page if scope grows.

Decision Needed
- Approve adding a supervisor subsection to the Iterative Agent reference.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: A compact “Supervisor runner” subsection was added under CLI usage with core flags and an example.
**Evidence**: `docs/reference/iterative-agent-behavior.md` includes a Supervisor runner subsection listing provider/model and tool toggle flags with citations to the runner and utils (L98–L111). 【F:docs/reference/iterative-agent-behavior.md‑ L98-L111】
**Conclusion**: Supervisor flags coverage is now present on the Iterative Agent reference page.

</details>

### Q2 — Docs Placement (Getting Started vs Reference)

Question
- Should key Iterative Agent flags/workflows appear in Getting Started, or remain only in Reference?

Background
- Examples link to the reference page for flags; Getting Started currently lacks an iterative quick‑start snippet.

Options
- A) Add a small Getting Started card with a 3‑line example and a link to the reference.
- B) Keep flags only in the reference to avoid duplication.

Trade‑offs
- A increases approachability but can drift from reference; B avoids drift but may slow first‑time onboarding.

Proposed Direction
- A. Add a single short example and a link; no inline flag tables in Getting Started.

Decision Needed
- Approve adding the Getting Started card and link.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Added an “Iterative Quick Start” snippet with a minimal command and tips.
**Evidence**: `docs/getting-started/inspect_agents_quickstart.md` includes a new section with `uv run python examples/runners/iterative_runner.py --time-limit 300 --max-steps 20 ...` and notes on provider/model, limits, and tool flags.
**Conclusion**: Quick-start card present; Getting Started now covers both supervisor and iterative flows.

</details>

### Q3 — Default Budgets (Time/Steps)

Question
- Should we standardize `time_limit`/`max_steps` defaults across runners and examples?

Background
- `run_iterative.py` and `iterative_task.py` default to 600s/40 steps; `run_profiled.py` defaults to 120s/20 steps. Docs examples now commonly show 300s/20 steps for snappier runs.

Options
- A) Unify all scripts at 300s/20.
- B) Keep script defaults (600/40 for general, 120/20 for profiled) but standardize docs at 300/20.
- C) Unify all scripts at 600/40 and advise users to lower via flags for quick runs.

Trade‑offs
- Short budgets speed iteration but risk truncation; longer budgets improve result quality but cost time/resources.

Proposed Direction
- B. Standardize documentation examples at 300/20; revisit script defaults after user feedback.

Decision Needed
- Approve documentation standard of 300/20 and defer script changes.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Documentation now standardizes example budgets at `--time-limit 300` and `--max-steps 20` for quick runs.
**Evidence**: Iterative reference includes a note recommending 300/20 (Quick Reference). 【F:docs/reference/iterative-agent-behavior.md‑ L21】 Getting Started adds an “Iterative Quick Start” using 300/20. 【F:docs/getting-started/inspect_agents_quickstart.md‑ L129-L137】
**Conclusion**: Documentation standardization applied (scripts retain their original defaults).

</details>

### Q4 — CI/Test Scope for Docs‑Only PRs

Question
- What subset of tests should run automatically for docs‑only changes?

Background
- We’ve been running targeted unit subsets locally (e.g., `tests/unit/inspect_agents -k iterative`) due to sandbox constraints and time budgets.

Options
- A) Add a docs‑only CI job that runs a fast unit subset offline plus a link checker.
- B) Skip tests on docs‑only PRs and rely on maintainers to opt‑in runs.

Trade‑offs
- A increases confidence with modest CI cost; B is cheaper but risks unnoticed drift.

Proposed Direction
- A. Add a unit subset (`iterative or tools or logging`), offline env, `--maxfail=1`.

Decision Needed
- Approve adding the docs‑only CI job.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Docs‑only CI now runs a fast unit subset; the main test workflow skips on docs‑only PRs via path filters.
**Evidence**: `.github/workflows/docs.yml` adds a `unit-subset` job for pull requests that runs `pytest -k "iterative or tools or logging"` with offline env. `.github/workflows/tests.yml` adds `paths-ignore` for `docs/**` and `mkdocs.yml` under `pull_request`. 【F:.github/workflows/docs.yml‑ L74-L96】【F:.github/workflows/tests.yml‑ L1-L12】
**Conclusion**: Docs‑only CI policy implemented: docs build + fast unit subset; full tests skipped for docs‑only PRs.

</details>

### Q5 — CLI Quick Reference Table

Question
- Should the Iterative Agent reference include a compact flag table at the top?

Background
- The page contains prose and examples; a table may speed scanning for experienced users.

Options
- A) Add a two‑column table (Flag → Description/Default) for core flags and task `-T` equivalents.
- B) Rely on prose/examples and `--help` output.

Trade‑offs
- Tables can drift from CLI help; prose is harder to scan.

Proposed Direction
- A. Add the table with a note that `--help` is the source of truth.

Decision Needed
- Approve adding the quick‑reference table.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: A compact “Quick Reference” table was added near the top of the Iterative Agent reference summarizing key flags and env mappings.
**Evidence**: `docs/reference/iterative-agent-behavior.md` includes a table covering `--time-limit`, `--max-steps`, provider/model flags, and common env toggles. 【F:docs/reference/iterative-agent-behavior.md‑ L9-L16】
**Conclusion**: Quick reference present; improves scanability for operators.

</details>

### Q6 — Cross‑Linking Between Reference and Examples

Question
- Where should backlinks live for best navigation?

Background
- Examples link to the reference; the reference can add a “See Also” section to point to research runners and the Inspect task.

Options
- A) Add a short “See Also” at the bottom of the reference with 2–3 high‑value links.
- B) Add inline links next to each CLI subsection heading.

Trade‑offs
- A keeps the page clean; B increases inline navigation but can be noisy.

Proposed Direction
- A. Add a concise “See Also” block.

Decision Needed
- Approve adding the “See Also” links.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Added a concise “See Also” block linking to Environment reference, Settings API, Supervisor guide, and tool umbrellas.
**Evidence**: `docs/reference/iterative-agent-behavior.md` now includes a “See Also” section with links. 【F:docs/reference/iterative-agent-behavior.md‑ L82-L88】
**Conclusion**: Cross‑links present; navigation improved.

</details>

### Q7 — Additional Example: `INSPECT_MAX_TOOL_OUTPUT`

Question
- Should we include a sample command setting the global tool‑output cap in the examples?

Background
- The reference documents `INSPECT_MAX_TOOL_OUTPUT`; examples do not yet show it in command lines.

Options
- A) Add one example using `INSPECT_MAX_TOOL_OUTPUT=8192` with a short note on provider behavior and wrappers.
- B) Keep this detail in configuration prose only.

Trade‑offs
- A improves visibility of limits; risks implying provider‑uniform behavior where differences exist.

Proposed Direction
- A. Add a single example with a cautionary note and link to provider/tool specifics.

Decision Needed
- Approve adding the example to the Iterative Agent reference.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Added a concrete inline example to the Iterative Agent reference under “Tool‑Output Truncation”.
**Evidence**: `docs/reference/iterative-agent-behavior.md` includes a command block setting `INSPECT_MAX_TOOL_OUTPUT=8192` and running the iterative runner (L27–L35). Environment reference still shows example exports (8192 and 0). 【F:docs/reference/iterative-agent-behavior.md‑ L27-L35】【F:docs/reference/environment.md‑ L588-L595】
**Conclusion**: Completed — both Environment and Iterative references now include examples.

</details>

---

## Model Resolver Diagnostics (`resolve_model_explain`) — Open Questions

Context (2025-09-04)
- We added `resolve_model_explain(provider=None, model=None, role=None)` which returns `(model_id, explain_dict)` for deterministic testing and debugging without scraping logs. The dict mirrors `_log_model_debug` fields and includes `path`. This preserves `resolve_model(...)` behavior and logging. See `src/inspect_agents/model.py` for the helper `_resolve_model_core(...)` and the public function.  

Why this matters
- Tests and operators need structured, assertion-friendly insight into how a model was resolved: which inputs were considered, where each choice came from (arg/env/default/role), and which branch produced the final value.
- Stabilizing the debug surface avoids brittle log scraping and provides hooks for CI and support tooling.

### 1) What fields belong in the explain dict by default?

Current
- Explain dict contains: `path`, `provider_arg`, `model_arg`, `role_env_model`, `role_env_provider`, `env_inspect_eval_model`, plus `final` (added on return).

Options
- Minimal (status quo): keep only inputs + `path` + `final`.
- Enriched: add normalized, post-resolution fields and sources:  
  - `provider_effective` (normalized provider actually used)  
  - `provider_source` (`arg|env|default|role-map`)  
  - `model_effective` (bare tag used in provider-specific branches when applicable)  
  - `model_source` (`arg|env|role-map|inspect-eval`)  
  - Echo `role` for downstream assertions.

Recommendation
- Adopt Enriched; keep existing keys for backward compatibility and add new keys with stable semantics.

Acceptance Criteria
- Add the enriched keys; update reference docs; add unit tests asserting values and `*_source` labels across explicit, role-map, INSPECT_EVAL_MODEL, and provider branches.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: A typed explain surface is implemented via `resolve_model_explain(...)` returning `(final: str, trace: ModelResolutionTrace)`. Each `ModelResolutionStep` in the trace includes `path`, `provider_arg`, `model_arg`, `role`, `role_env_model`, `role_env_provider`, `env_inspect_eval_model`, and optional `final_candidate`.
**Evidence**: `src/inspect_agents/model.py` — `ModelResolutionStep` and `ModelResolutionTrace` definitions (L86–L109), `resolve_model_explain(...)` (L143–L231, L233–L389). Unit tests exercise the API and step labels in `tests/unit/inspect_agents/test_model_resolver.py` (e.g., explicit path, role mapping, env override, vendor branches).
**Conclusion**: Explain surface is implemented with a typed trace (enriched fields). Remaining enrichment keys like `*_source` are optional enhancements (see item 4 below).

</details>

### 2) Error explainability — how to surface context on failures?

Current
- `RuntimeError` is raised for missing API keys or tags on remote providers; message is human-readable but unstructured.

Options
- Keep plain exceptions.  
- Introduce `ModelResolutionError` carrying `.explain` (dict) and `.reason` (`missing_api_key|missing_model|invalid_provider|...`).

Recommendation
- Introduce `ModelResolutionError` while preserving message text; keep `resolve_model()` return type unchanged.

Acceptance Criteria
- Replace `RuntimeError` raises with `ModelResolutionError(reason=..., explain=...)`; add tests for missing API key (openai), missing model (openai), and `openai-api/<vendor>` missing vendor key.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Errors use a typed exception `ResolveModelError` that carries `.final_step` and a full `.trace`. The public `resolve_model(...)` wrapper preserves legacy behavior by catching `ResolveModelError` and re-raising `RuntimeError` with the same message.
**Evidence**: `src/inspect_agents/model.py` `class ResolveModelError` (L111–L117); provider branches raising `ResolveModelError` (e.g., L295–L312, L333–L349); wrapper re-raising `RuntimeError` (L415–L420).
**Conclusion**: Typed error with structured context is implemented while maintaining backwards-compatible external exceptions from `resolve_model(...)`.

</details>

### 3) Path label stability — public contract or best-effort?

Current
- Labels include: `explicit_model_with_provider`, `role_env_mapping`, `role_inspect_indirection`, `env_INSPECT_EVAL_MODEL`, `provider_ollama`, `provider_lm_studio`, `provider_<remote>`, `provider_openai_api_<vendor>`, `fallback_model_with_provider`, `final_fallback_ollama`.

Options
- Treat as internal (no guarantees).  
- Freeze as public; only additive changes; deprecations documented.

Recommendation
- Freeze current set as public; allow additive changes only; document deprecations with a minor version bump.

Acceptance Criteria
- Document label list; add a smoke test asserting label membership for common scenarios.

<details>
<summary>✅ Answer Found (Partial)</summary>

**Finding**: A smoke test asserts that the final `trace.steps[-1].path` belongs to a known set of labels across common scenarios, providing guardrails without freezing the labels as public constants.
**Evidence**: `tests/unit/inspect_agents/model/test_model_labels_smoke.py` defines `ALLOWED_LABELS` and exercises explicit model, role indirection, env override, default/fallback, vendor, and fallback-with-provider cases. 【F:tests/unit/inspect_agents/model/test_model_labels_smoke.py‑ L1-L22】【F:tests/unit/inspect_agents/model/test_model_labels_smoke.py‑ L24-L70】 Code sets these labels within `resolve_model_explain(...)` as previously cited in `src/inspect_agents/model.py`.
**Conclusion**: Minimal stability guarantee via tests is in place; labels remain internal (not exported) unless a future decision elevates them to a public contract.

</details>

⚠️ Still Open - Requires Decision
- Decide whether to freeze `path` labels as a public, versioned
  contract (additive-only), or keep them internal with smoke-test
  guarantees only.

### 4) Source granularity — record where each decision came from?

Current
- Not explicitly recorded beyond raw inputs.

Options
- Add `provider_source`, `model_source`, `role_source`, and `inspect_eval_source` (`unset|sentinel|set`).

Recommendation
- Add these keys; high debug value, low cost.

Acceptance Criteria
- Tests assert `*_source` values for arg/env/default/role-map branches.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: The explain trace now records `provider_source`, `model_source`, `role_source`, and `inspect_eval_source` (unset|sentinel|set).
**Evidence**: `src/inspect_agents/model.py` extends `ModelResolutionTrace` with these fields and sets them in explicit, role-map, inspect-eval, provider, fallback, and final fallback branches. 【F:src/inspect_agents/model.py‑ L96-L112】【F:src/inspect_agents/model.py‑ L270-L283】【F:src/inspect_agents/model.py‑ L285-L306】【F:src/inspect_agents/model.py‑ L338-L362】【F:src/inspect_agents/model.py‑ L405-L410】【F:src/inspect_agents/model.py‑ L429-L443】 Smoke tests assert basic provenance in common scenarios. 【F:tests/unit/inspect_agents/model/test_model_sources.py‑ L1-L16】【F:tests/unit/inspect_agents/model/test_model_sources.py‑ L18-L36】
**Conclusion**: Source-granularity fields implemented with initial test coverage; more scenarios can be added over time.

</details>

### 5) Sentinel handling for `INSPECT_EVAL_MODEL=none/none`

Current
- Sentinel disables the env override but is not explicitly surfaced beyond omission.

Options
- Add `inspect_eval_disabled: bool` and `env_inspect_eval_model_raw`.

Recommendation
- Add both; keep `env_inspect_eval_model` as the effective value or `None`.

Acceptance Criteria
- Test that with `none/none`, `inspect_eval_disabled is True`, `env_inspect_eval_model is None`, and `*_raw == "none/none"`.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: The explain trace now surfaces `inspect_eval_disabled` and `env_inspect_eval_model_raw` (normalized) alongside steps and final.
**Evidence**: `src/inspect_agents/model.py` extends `ModelResolutionTrace` with these fields and sets them based on `INSPECT_EVAL_MODEL` (lowercased, stripped); sentinel `none/none` sets `inspect_eval_disabled=True`. 【F:src/inspect_agents/model.py‑ L103-L112】【F:src/inspect_agents/model.py‑ L211-L218】 Unit tests assert flags for multiple sentinel variants. 【F:tests/unit/inspect_agents/model/test_model_resolver_sentinel_flags.py‑ L1-L20】【F:tests/unit/inspect_agents/model/test_model_resolver_sentinel_flags.py‑ L22-L37】
**Conclusion**: Sentinel handling is explicit and test‑backed while preserving existing resolver behavior.

</details>

### 6) Type shape — dict vs typed object

Current
- Return type is `(str, dict)`.

Options
- Keep dict; add `TypedDict` for static typing.  
- Switch to `NamedTuple`/`@dataclass` (breaking change) or provide an optional wrapper factory.

Recommendation
- Add a `TypedDict` and keep returning a dict; optionally expose a dataclass factory without changing the default return.

Acceptance Criteria
- Type stubs + mypy annotations; docs list keys and meanings.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Type shape is a pair `(str, ModelResolutionTrace)` using dataclasses, not a dict. The trace contains a list of `ModelResolutionStep` entries plus `final`.
**Evidence**: `src/inspect_agents/model.py` `ModelResolutionTrace` (L103–L109) and `resolve_model_explain(...) -> tuple[str, ModelResolutionTrace]` (L143–L151, L147–L148 signature).
**Conclusion**: The project chose a typed dataclass trace over a plain dict. Documentation reflects this in a dedicated how-to page.

</details>

### 7) Test coverage — offline-safe additions

Gaps
- Remote providers with placeholder keys, `openai-api/<vendor>` branch, and sentinel case.

Plan
- Add tests for: `openai` with fake key; `openai-api/lm-studio` with fake key/model; sentinel `none/none`; role-map with provider split; fallback with bare model. Ensure `NO_NETWORK=1`.

Acceptance Criteria
- Deterministic pass with no network; failures report specific `path` and `*_source`.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Dedicated offline-safe tests cover the explain surface, branch labels, sentinel handling, vendor branches, and error paths.
**Evidence**: `tests/unit/inspect_agents/test_model_resolver.py` asserts `trace.steps[-1].path` across scenarios and validates `ResolveModelError` carries a trace.
**Conclusion**: Coverage is in place and deterministic (uses env monkeypatching, no network).

</details>

### 8) Docs placement — where to teach debugging

Current
- Brief note exists in `docs/reference/environment.md` under Providers & Models.

Options
- Add a short “Debugging model resolution” page under `docs/how-to/`.  
- Add an example in `examples/research/README.md`.

Recommendation
- Do both; keep the how-to concise and link to reference and examples.

Acceptance Criteria
- New how-to exists; examples updated; cross-links present from the reference page.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: A dedicated how-to documents the explain API with examples; the symbols are also exported from the package root for discoverability.
**Evidence**: `docs/how-to/model_resolver_explain.md` (API, examples); exports in `src/inspect_agents/__init__.py` include `resolve_model_explain`, `ResolveModelError`, and trace types.
**Conclusion**: Documentation for model-resolution debugging is present; cross-links can be expanded later as needed.

</details>

Related files
- Implementation: `src/inspect_agents/model.py` (resolver + explain helper).  
- Tests: `tests/unit/inspect_agents/model/test_model_explain.py`, `tests/unit/inspect_agents/model/test_model.py`.  
- Docs: `docs/reference/environment.md` (reference note), this file.

---

# Settings and Env Centralization — Open Questions (2025‑09‑04)

Context
- We introduced `src/inspect_agents/settings.py` to centralize common env/flag parsing and reduce drift across modules. Internal helpers in `tools.py`, `tools_files.py`, `filters.py`, and `approval.py` now delegate to it via aliases that preserve historical underscore names for test monkeypatching.

## 1) Filters aliasing vs wrapper for `_truthy`

- Current state: `filters.py` assigns `_truthy = settings.truthy` (no redefinition).
- Why it matters: tests patch `_truthy`; aliasing avoids code duplication and drift.
- Options:
  - A) Keep alias (status quo).
  - B) Replace with a wrapper function calling `settings.truthy(val)`.
- Recommendation: A) keep alias — minimal surface, fully patchable.
- Exit criteria: Document policy in `docs/reference/environment.md`; avoid redefining `_truthy` elsewhere.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: `filters.py` delegates via an alias, not a wrapper: `_truthy = _settings_truthy`.
**Evidence**: See `src/inspect_agents/filters.py` (compat alias set once; callers use `_truthy`).
**Conclusion**: Option A implemented (keep alias). Docs can optionally call this out.

</details>

## 2) Iterative helpers migration (`iterative_config.py`)

- Current state: local `_parse_int_opt` returns `None` for non‑positive values; semantics differ slightly from `settings.int_env` with `minimum`.
- Why it matters: we must not change meaning of “disabled” (<=0 → None) when consolidating.
- Options:
  - A) Leave as‑is.
  - B) Add tiny wrappers that call `settings.int_env` then convert `<=0` → None.
  - C) Extend `settings.int_env` with a `none_if_leq` option and adopt it.
- Recommendation: B) wrappers in `iterative_config.py` now; consider C) if pattern repeats elsewhere.
- Exit criteria: wrappers in place; iterative tests green with unchanged behavior.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Time/step and truncation helpers now delegate env parsing to `settings.int_env` via a local `_pos_env()` wrapper that converts `<=0` to `None`.
**Evidence**: `src/inspect_agents/iterative_config.py` imports `int_env` and implements `_pos_env(...)` (lines 14–26). `resolve_time_and_step_limits(...)` and `resolve_truncation(...)` call `_pos_env(...)` for `INSPECT_ITERATIVE_TIME_LIMIT`, `INSPECT_ITERATIVE_MAX_STEPS`, `INSPECT_PER_MSG_TOKEN_CAP`, and `INSPECT_TRUNCATE_LAST_K`. 【F:src/inspect_agents/iterative_config.py‑ L13-L26】【F:src/inspect_agents/iterative_config.py‑ L33-L41】【F:src/inspect_agents/iterative_config.py‑ L45-L53】【F:src/inspect_agents/iterative_config.py‑ L95-L103】【F:src/inspect_agents/iterative_config.py‑ L109-L116】
**Conclusion**: Wrappers in place; semantics unchanged; unit tests for iterative_config pass.

</details>

## 3) `str_env` empty‑string semantics

- Current state: `str_env(name, default)` returns empty string if set; only uses default when unset.
- Why it matters: some call-sites may want “empty means unset”.
- Options:
  - A) Keep current behavior universally (empty ≠ unset).
  - B) Add `str_env_or_none(name)` that collapses empty/whitespace to None; use selectively.
- Recommendation: A) keep; introduce B) only when needed by real callers.
- Exit criteria: document rule; audit provider selection code paths.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: `str_env(name, default)` returns empty string when set; defaults only when unset.
**Evidence**: `src/inspect_agents/settings.py` `str_env(...)` returns `default if val is None else val`.
**Conclusion**: Option A implemented (empty ≠ unset). No additional helper present.

</details>

## 4) Filesystem knobs centralization

- Current state: FS envs (`INSPECT_AGENTS_FS_MODE`, `_FS_ROOT`, `_FS_MAX_BYTES`, `_FS_READ_ONLY`) live in FS modules to avoid cycles and keep sandbox logic cohesive.
- Options:
  - A) Keep local (status quo).
  - B) Move pure getters to `settings` and import from FS code.
- Risks: potential import cycles and heavier import‑time behavior.
- Recommendation: A) keep local; revisit B) after confirming no cycles and measuring impact.
- Exit criteria: rationale documented; no duplicate FS parsing outside FS modules.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: FS env parsing (`INSPECT_AGENTS_FS_*`) lives in the FS layer; callers import via `inspect_agents.fs` or adapter.
**Evidence**: `src/inspect_agents/fs.py` implements `fs_mode/fs_root/max_bytes/default_tool_timeout`; `src/inspect_agents/tools_files.py` binds to these helpers.
**Conclusion**: Option A implemented (keep local to FS modules).

</details>

## 5) Tool‑output cap (`INSPECT_MAX_TOOL_OUTPUT`) accessor

- Current state: parsed in multiple places (observability, iterative) with defensive merges into Inspect `GenerateConfig`.
- Proposal: add `settings.max_tool_output_env() -> int | None` parsing non‑negative ints (0 allowed) and returning None when unset/invalid.
- Recommendation: add accessor; adopt in both call sites without changing precedence (explicit arg/active config still beat env).
- Exit criteria: unified accessor in place; limit/truncation tests remain green.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Central accessor implemented and adopted at both call sites.
**Evidence**: `src/inspect_agents/settings.py` adds `max_tool_output_env()` returning `int|None` (non-negative, `0` allowed) (L61–L79, L83–L90). `src/inspect_agents/observability.py` now calls `_max_tool_output_env()` in both the one‑time emitter and the side‑effect‑free getter (L54–L56→refactored, L109–L117→refactored). `src/inspect_agents/iterative.py` uses `_max_tool_output_env()` for the early precedence merge (L336→refactored).
**Conclusion**: Option implemented with no precedence changes; tests covering effective limit and gating should remain green.

</details>

## 6) Unit tests for `settings`

- Current state: behavior covered indirectly; no direct tests for helpers.
- Action: add `tests/unit/inspect_agents/config/test_settings.py` covering `truthy`, `int_env` (min/max and invalid), `float_env` (invalid), `str_env`, `typed_results_enabled`, `default_tool_timeout`.
- Exit criteria: tests green offline; examples documented in `tests/README.md`.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: A dedicated unit test module validates settings helpers, including the new `max_tool_output_env()` accessor.
**Evidence**: `tests/unit/inspect_agents/config/test_settings.py` covers `truthy`, `int_env` (min/max and invalid), `float_env`, `str_env` (empty vs unset), `typed_results_enabled`, `default_tool_timeout`, and `max_tool_output_env` edge cases. 【F:tests/unit/inspect_agents/config/test_settings.py‑ L1-L29】【F:tests/unit/inspect_agents/config/test_settings.py‑ L31-L90】
**Conclusion**: Tests in place; semantics are pinned and offline‑safe.

</details>

## 7) Deprecation path for underscore helpers

- Current state: underscore names remain as import aliases for patchability.
- Recommendation: soft‑deprecate in comments; prefer `settings.*` in new code; keep aliases long‑term to avoid breaking tests.
- Exit criteria: internal call‑sites use `settings.*`; aliases retained for back‑compat.

<details>
<summary>✅ Answer Found (Partial)</summary>

**Finding**: Underscore aliases exist without warnings (soft deprecation only in comments/doc intent).
**Evidence**: `src/inspect_agents/fs.py` exports `_truthy = truthy` and other underscore aliases; no warnings emitted.
**Conclusion**: Current state matches the first phase (silent aliases). Formal deprecation timeline/warnings not yet implemented.

</details>


## 8) Documentation touchpoints

- Current state: `settings.py` exists; not yet surfaced in docs.
- Actions: add an “Environment & Settings” section to `docs/reference/environment.md`; cross‑link from quickstart and approvals how‑to.
- Exit criteria: docs updated; code snippets use `settings.*`.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: The Environment reference now includes an “Environment & Settings API” section that points to the centralized helpers and API docs.
**Evidence**: `docs/reference/environment.md` adds a section with guidance and a link to the API page (L177–L185). API page exists at `docs/api/settings.md` with autogenerated entries.
**Conclusion**: Documentation touchpoint complete; code should prefer `inspect_agents.settings`.

</details>

## 9) Deprecation signaling (warnings) for `_truthy`

- Current state: `fs.py` now delegates `truthy` to `settings.truthy` and exports `_truthy = truthy` for compatibility. No deprecation warnings are emitted.
- Why it matters: we want to encourage migration without introducing log noise or breaking tests that treat warnings as errors.
- Options:
  - A) Keep silent alias for one release; document removal timeline.
  - B) Emit a `DeprecationWarning` once per process on first alias access; keep alias for N cycles.
  - C) Gate warnings behind `INSPECT_SHOW_DEPRECATIONS=1` (opt‑in), keeping default runs quiet; switch to B next cycle.
- Recommendation: C → B → removal. Start with opt‑in warnings this cycle, default warnings next, then remove alias in the following release.
- Exit criteria: deprecation policy documented; env flag recognized; downstream repos migrate to `settings.truthy` or `fs.truthy`.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: Opt‑in deprecation warnings are implemented for underscore aliases via `INSPECT_SHOW_DEPRECATIONS=1`, emitted once per alias per process.
**Evidence**: `src/inspect_agents/fs.py` wraps `_fs_mode`, `_use_sandbox_fs`, etc., to call the non‑underscore variants and warn once when `INSPECT_SHOW_DEPRECATIONS` is truthy. `src/inspect_agents/filters.py` wraps `_truthy` similarly. 【F:src/inspect_agents/fs.py‑ L243-L287】【F:src/inspect_agents/filters.py‑ L25-L32】【F:src/inspect_agents/filters.py‑ L36-L56】 Unit test `test_deprecations_gating.py` asserts no warnings by default and single warnings when enabled. 【F:tests/unit/inspect_agents/config/test_deprecations_gating.py‑ L1-L16】【F:tests/unit/inspect_agents/config/test_deprecations_gating.py‑ L18-L35】
**Conclusion**: Deprecation policy (opt‑in) is encoded; we can switch to default‑on warnings in a future cycle.

</details>

## 10) Standardize `env_templates/configure.py` truthy semantics

- Current state: configurator accepts `"y"/"Y"` in addition to the canonical set (`{"1","true","yes","on"}`) used by runtime parsing. Divergence is limited to this interactive script.
- Why it matters: differences between template UX and runtime can confuse users reading docs/examples.
- Options:
  - A) Standardize now by importing `settings.truthy` (drop `"y"`).
  - B) Keep `"y"` as an interactive convenience but document that runtime accepts only the canonical set; optionally rename helper to `ui_truthy` for clarity.
  - C) Expand runtime `settings.truthy` to include `"y"` (cross‑cutting behavior change; not recommended this cycle).
- Recommendation: B — keep the UX convenience localized to the configurator, add a short note in environment docs about the canonical runtime set.
- Exit criteria: configurator helper renamed/commented; docs updated; no changes to runtime semantics.

<details>
<summary>✅ Answer Found in Implementation</summary>

**Finding**: The configurator intentionally accepts `"y"` in addition to the canonical set used at runtime.
**Evidence**: `env_templates/configure.py` `_truthy` includes `"y"`; runtime parsing in `src/inspect_agents/settings.py::truthy` uses `{ "1", "true", "yes", "on" }` only.
**Conclusion**: Option B implemented (keep interactive convenience localized; runtime remains canonical). A short docs note can be added later.

</details>
