# TODO: Sandbox — Best Practices Feature Set

Status: PROPOSED (2025-09-08)

This epic groups production‑readiness features for sandboxing across filesystem (FS), providers, network isolation, approvals, observability, and UX. Each item below is self‑contained and actionable.

---

## 1) Sandbox Profiles (Tx.Hx.Nx) As First‑Class Config

### Context & Motivation
- Purpose: selectable security profiles for Tooling (T), Host isolation (H), and Network (N) to make runs consistent, auditable, and safe by default.
- Problem: manual wiring of env flags/sandbox providers is error‑prone and unaudited.
- Background: profiles are documented; we need lightweight application‑layer wiring.

### Implementation Guidance
- Examine: `src/inspect_agents/run.py`, `docs/guides/sandbox_profiles.md`, `docs/how-to/inspect_sandbox.md`.
- Grep: `INSPECT_ENABLE_EXEC`, `INSPECT_ENABLE_WEB_SEARCH`, `INSPECT_ENABLE_WEB_BROWSER`, `approval_preset`, `sandbox=`.
- Add helper (new `profiles.py` or inside `run.py`) to parse `INSPECT_PROFILE=T{0..2}.H{0..3}.N{0..2}`, set tool toggles and Task `sandbox`, and log profile metadata.

### Scope Definition
- New profile parser + applier; emit a `tool_event` enriched with `profile`.
- No changes to low‑level tools or Inspect upstream.

### Success Criteria
- Setting `T1.H1.N2` enables web‑only tools, selects docker sandbox, and logs the profile.
- Unit test for parser + smoke test asserting toggles and event payload.

---

## 2) Provider Hardening Templates (Docker/K8s/VM)

### Context & Motivation
- Purpose: ship secure‑by‑default provider configs aligned to profiles.
- Problem: ad‑hoc configs weaken isolation.

### Implementation Guidance
- Add: `ops/providers/docker/compose.yaml` (rootless user, read‑only FS, minimal caps, seccomp) and `ops/providers/k8s/values.yaml` (PodSecurity, fsGroup, readOnlyRootFilesystem, resources, NetworkPolicy stubs).
- Docs: README in each provider with usage and Inspect wiring.

### Scope Definition
- Templates + docs only; no Python changes.

### Success Criteria
- Compose/Helm render and run; docs provide step‑by‑step usage.

---

## 3) Network Isolation Presets (N1/N2)

### Context & Motivation
- Purpose: enforce domain allow‑lists (N1) or zero egress (N2).
- Problem: Docker defaults to open egress; K8s needs explicit policy.

### Implementation Guidance
- K8s: NetworkPolicy snippets in `ops/providers/k8s/values.yaml` for N1/N2; domain list injection.
- Docker: document proxy/custom network approach in provider README; optional example network.

### Scope Definition
- Wire presets as values/comments; later consumed by E2E tests.

### Success Criteria
- K8s values render valid policies; negative fetch tests fail under N1/N2.

---

## 4) Atomic FS Writes + Per‑Path Async Locks

### Context & Motivation
- Purpose: prevent torn writes/races for write/edit.
- Problem: concurrent ops can interleave.

### Implementation Guidance
- Modify `src/inspect_agents/tools_files.py`: wrap `execute_write`/`execute_edit` in per‑path `anyio.Lock()`; implement temp‑file + atomic rename for both store and sandbox (adapter uses `mv`).
- Grep: `execute_write`, `execute_edit`, `anyio.fail_after`, `store_as(Files)`.

### Scope Definition
- Add singleton lock map; critical section around mutation; same size/time caps.

### Success Criteria
- Concurrency test: parallel edits produce ordered, non‑interleaved content; no deadlocks.

---

## 5) Directory/Metadata Operations (mkdir/move/stat)

### Context & Motivation
- Purpose: provide common file ops with same guardrails.

### Implementation Guidance
- Update `src/inspect_agents/tools_files.py` (new commands/params) and `src/inspect_agents/fs_adapter.py` (bash/editor variants).
- Enforce: root confinement and symlink denial before action.

### Scope Definition
- Implement `mkdir`, `move`, `stat` with typed results; store‑mode minimal semantics.
- Avoid enabling host delete.

### Success Criteria
- Round‑trip tests pass (sandbox + store) with traversal/symlink guards.

---

## 6) Path Policy Engine (Allow/Deny Globs)

### Context & Motivation
- Purpose: fine‑grained subtree control beyond root confinement.

### Implementation Guidance
- Add to `src/inspect_agents/fs.py`: parse `INSPECT_FS_ALLOW`/`INSPECT_FS_DENY` (comma‑separated globs), `check_policy(abs_path)` after normalization.
- Call from write/edit/mkdir/move/trash before adapter.

### Scope Definition
- Policy relative to `fs_root()`; read/ls policy optional.

### Success Criteria
- Allowed paths succeed; denied paths raise with audited rule match.

---

## 7) Audited “Trash” Delete (Sandbox Mode)

### Context & Motivation
- Purpose: reversible, auditable deletion without enabling hard delete.

### Implementation Guidance
- Add `trash` command in `tools_files.py`; move target to `fs_root()/.trash/<ts>/<rel_path>` via adapter (`mkdir -p` + `mv`).
- Keep `delete` in sandbox raising `SandboxUnsupported`.

### Scope Definition
- New command only; require approval in dev/prod.

### Success Criteria
- Tests verify file moved and audit event emitted with original/trash paths.

---

## 8) Stronger Safe Defaults (Prod)

### Context & Motivation
- Purpose: safer defaults for prod profiles.

### Implementation Guidance
- In profile applier: when H≥H1, default `INSPECT_AGENTS_FS_READ_ONLY=1` and `INSPECT_SANDBOX_PREFLIGHT=force` unless explicitly set.

### Scope Definition
- Profile‑driven only; dev unchanged.

### Success Criteria
- Under prod profile, sandbox write/edit fail with `SandboxReadOnly` unless overridden.

---

## 9) Approval Enforcement For FS Mutations

### Context & Motivation
- Purpose: approvals for sandbox mutations (write/edit/mkdir/move/trash).

### Implementation Guidance
- Extend sensitive regex in `src/inspect_agents/approval/presets.py` to include `files` mutation commands; reuse redaction in explanations.

### Scope Definition
- CI preset unchanged; enforce in dev/prod chains.

### Success Criteria
- Tests: FS mutations escalate/terminate under dev/prod; logs include redacted args.

---

## 10) Preflight Status‑Change Events

### Context & Motivation
- Purpose: log structured events when sandbox availability flips.

### Implementation Guidance
- Modify `src/inspect_agents/fs.py` `ensure_sandbox_ready`: track last status and emit `phase="status_changed"` payload on flip (with env ID if available).

### Scope Definition
- Logging only; preserve current behavior and TTL cache.

### Success Criteria
- Tests simulate down→up→down with small TTL; one change event per flip.

---

## 11) Tamper‑Evident Audit Trail

### Context & Motivation
- Purpose: signed hash chain for transcript/audit logs plus richer context.

### Implementation Guidance
- Add `write_transcript_secure()` in `src/inspect_agents/logging.py` that writes JSONL with `prev_hash`/`hash` over canonicalized fields; include `profile`, `fs_root`, approver, path, bytes.
- Optionally enrich `tool_event` payloads in mutation paths.

### Scope Definition
- New writer; keep existing `write_transcript` intact.

### Success Criteria
- Verification utility confirms chain integrity; tampering detection works.

---

## 12) Streaming Reads (Large Files)

### Context & Motivation
- Purpose: chunked reads to bound memory/time while honoring limits.

### Implementation Guidance
- Add `view_chunks()` to `src/inspect_agents/fs_adapter.py` using `sed -n` ranges; update `execute_read` to iterate chunks until `limit` reached; keep 2000‑char/line cap.

### Scope Definition
- Sandbox mode first; store mode unchanged.

### Success Criteria
- Large file read stays within timeout/memory and returns correct numbering/limits.

---

## 13) Shell‑Out Hardening Audit

### Context & Motivation
- Purpose: ensure all shell calls are properly quoted/minimal.

### Implementation Guidance
- Audit `src/inspect_agents/fs_adapter.py` and `src/inspect_agents/fs.py` for `bash(action="run"...)`; enforce `shlex.quote` and minimal commands; extend fuzz tests for odd paths.

### Scope Definition
- No behavior change beyond safer quoting.

### Success Criteria
- Fuzzed path tests pass; no unquoted expansions remain.

---

## 14) End‑to‑End Provider Tests (Optional, Marked)

### Context & Motivation
- Purpose: validate real provider behavior for confinement, read‑only, and network.

### Implementation Guidance
- Add `tests/e2e/test_sandbox_docker.py` and `tests/e2e/test_sandbox_k8s.py` marked `@pytest.mark.sandbox_e2e`; consume provider templates; conservative timeouts.

### Scope Definition
- Optional; gated by marker and env prereqs.

### Success Criteria
- E2E suites pass locally/CI when enabled.

---

## 15) Runner/CLI Integration And UX

### Context & Motivation
- Purpose: one‑flag profile selection and actionable missing‑sandbox errors.

### Implementation Guidance
- Extend `run.py` to accept `profile` param/env; integrate with profiles applier; enrich error messages with fix hints.

### Scope Definition
- Additive API/env; default behavior unchanged.

### Success Criteria
- `--profile T0.H1.N1` configures sandbox/tools; missing sandbox shows guided fix.

---

## 16) Docs & Runbooks (Operational)

### Context & Motivation
- Purpose: concise runbooks for dev/research/prod with rollback and audit commands.

### Implementation Guidance
- Add `docs/runbooks/profile_dev.md`, `profile_research.md`, `profile_prod.md` with prerequisites, profile selection, provider setup, approvals, verification, rollback.

### Scope Definition
- Documentation only.

### Success Criteria
- Operators can enact/rollback profiles and validate audits without reading code.

---

## 17) Tool Event Enrichment With Profile Context

### Context & Motivation
- Purpose: include `profile` (and `fs_root` when enabled) on `files:*` events for audits.

### Implementation Guidance
- Attach `profile` to `extra` in observability calls within `tools_files.py` (or central logger wrapper) while respecting truncation settings.

### Scope Definition
- Logging only; avoid excessive payloads.

### Success Criteria
- `files:*` start/end/error events consistently include `profile` field.

---

## 18) Large‑File Performance Envelope (Complement to Streaming Reads)

### Context & Motivation
- Purpose: guarantee reads complete within time/size bounds consistently.

### Implementation Guidance
- Ensure chunk loop wraps each fetch in `anyio.fail_after(_default_tool_timeout())`; early byte‑cap gate via `wc -c` remains; keep 16 KiB global tool‑output envelope (Inspect default) documented.

### Scope Definition
- Sandbox mode only; formatting unchanged.

### Success Criteria
- Benchmarks: 5–10 MB files read within timeout and low memory; limits enforced.
