---
title: In‑Situ Self‑Improvement and Evaluation for Inspect Agents
status: Proposed
date: 2025-09-05
---

Context
Inspect Agents are intended for reproducible, sandboxed evaluation of agent behavior rather than open‑ended app development. Inspect‑AI already exposes auditable seams — tool approvals, structured tool_event logs, sandboxed tools, and a store‑backed state model — which together make it feasible to study agents that propose limited self‑modifications during a run and to measure their effects in situ.

In the upstream examples this pattern appears repeatedly:
- Approval Mode shows gating of risky actions and human escalation via YAML policies.
- Intervention and Computer/Browser demos reveal orchestration seams where intent → action → reflection can be observed and constrained.
- Bridge demos (LangChain, Codex/Claude Code) show how external agents can be wrapped and evaluated within Inspect.
- Eval sets demonstrate pre/post style execution across multiple tasks/models with persistent logs.

Problem & Goals
- Make “self‑improving” agent workflows evaluable inside the same framework that executes them.
- Ensure changes are safe, auditable, reproducible, and reversible.
- Prevent benchmark gaming by validating proposed changes on held‑out tasks with explicit acceptance criteria and rollback.

Decision
Adopt a configuration‑driven, approval‑gated self‑improvement workflow for Inspect Agents:

1) The running agent may propose a new agent configuration (YAML) that adjusts prompts, tool selections from an approved base set, and runtime limits. Proposals are written to the in‑memory Files store (or sandbox) via the unified files tool.

2) An approval chain (handoff exclusivity → parallel kill‑switch → repo policies) evaluates the proposal. Human approval can be placed last to resolve escalations.

3) If approved, the runner applies the configuration transactionally (parse → build agents → record version/hash). If parsing or safety checks fail, reject and revert.

4) Validate via a pre/post eval set on a fixed dataset and model set. Accept only when predefined thresholds are met (e.g., accuracy increases without exceeding a tool‑call or latency budget).

5) Persist transcripts, tool_event logs, approval decisions, and the before/after configs for audit and reproducibility. If metrics regress, automatically roll back to the previous accepted config.

Scope of Allowed Self‑Modifications (Phase 1)
- Allowed: supervisor prompt text; sub‑agent definitions (prompt/description and tool subset chosen from the base repo tools); per‑agent limits (time/messages/tokens); quarantine mode (strict/scoped) selection.
- Disallowed in‑situ: source code edits; adding new third‑party tools; filesystem destructive operations. These require a separate, human‑reviewed phase outside the in‑situ loop.

Architecture & Flow
- Proposal: controller writes a candidate YAML using `files` (command=write) into a well‑known path in the Files store.
- Gatekeeping: `approval_chain()` composes handoff exclusivity and the parallel kill‑switch with repo policies (allowlists for config writes). Human approver may be last‑resort.
- Apply: load YAML, construct agents via `build_supervisor()` and optional `build_subagents()`. Record a content hash/version for rollback.
- Evaluate: run an eval set against the current and proposed configs; compare task metrics and process metrics.
- Decide & Rollback: accept if thresholds met; else revert to previous config and record rationale.
- Observability: rely on structured tool_event logs and store‑change events; emit one‑time effective tool‑output limits for transparency.

Metrics & Acceptance Criteria
- Task metrics: correctness (exact/match/model‑graded), pass@k where relevant.
- Process metrics: tool‑call count, total tool output bytes, wall‑time, approval decisions (approve/modify/reject rates).
- Thresholds (example):
  - Primary: +Δaccuracy ≥ 2% on held‑out eval set.
  - Budgets: ≤ baseline tool‑calls and ≤ baseline p95 latency (or within +10%).
  - Stability: zero increase in approval rejections due to unsafe calls.

Safety & Reproducibility Measures
- Sandbox file ops; keep `delete` disabled in sandbox; prefer Files store for proposals.
- Keep handoff exclusivity and parallel kill‑switch enabled to reduce concurrency ambiguity in traces.
- Apply strict/scoped quarantine filters for sub‑agents; support per‑agent env overrides where isolation is needed.
- Version and persist the accepted config; record all env toggles used during evaluation.

Alternatives Considered
1) Unbounded code self‑modification: maximally flexible but irreproducible and unsafe without heavy isolation; rejected for phase 1.
2) Offline A/B only: simpler but loses the in‑situ visibility into process metrics and approval outcomes.
3) External RL/weight updates: out of scope for Inspect’s safety/eval mandate and introduces training governance concerns.

Consequences
- Pros: measurable, auditable improvements; clear rollback; consistent safety posture; easy reproduction.
- Cons: additional orchestration glue; potential slower iteration due to approvals and eval runs; limits the space of changes to configuration (by design).

Implementation Notes (Initial)
- Controller task: propose → gate → apply → eval → accept/reject; minimal Python glue can live alongside `inspect_agents.config` loader.
- Use existing repo presets for approval ordering and policies; add a tiny allowlist approver for config writes.
- Aggregate observability into a small metrics report (tool‑calls, bytes, durations, approval decisions) stored next to the config versions.
- Future: “bridge packs” to safely include LangChain/Claude/Codex bridges with default quarantine + limits, evaluated under the same loop.

Operational Guidance
- Start with prompts/tools/limits only; introduce code changes under explicit human change‑control in a separate phase.
- Rotate eval sets periodically to reduce overfitting; keep a frozen hold‑out for acceptance gates.
- Keep destructive and high‑risk tools disabled by default; require explicit opt‑in via policy + environment flags.

References
- ADR‑0003 Supervisor limits & observability
- ADR‑0004 Filesystem sandbox guardrails / Tool‑output truncation
- ADR‑0005 Tool parallelism policy
- ADR‑0006 Simple agent architecture
