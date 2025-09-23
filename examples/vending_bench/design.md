# Vending-Bench Implementation Design

## Overview
- Deliver a reproducible long-horizon benchmark where an Inspect agent operates a vending-machine business for hundreds of simulated days and tens of millions of tokens while tracking net worth, units sold, and tool efficiency.【F:examples/vending_bench/source_excerpts.md-L3-L6】
- The solution must pair a deterministic simulator with Inspect-compliant tooling and a supervisor plus sub-agent hierarchy to sustain coherent control over multi-day operations.【F:examples/vending_bench/source_excerpts.md-L7-L21】
- Implementation scope: develop Vending-Bench entirely under `examples/vending_bench/`, treating `inspect_agents` as an external dependency rather than modifying core packages.
- Establish a publicly consumable mirror repository for Vending-Bench artifacts to support versioned releases and external collaboration.

## Goals and Non-Goals
- **Goals:** Achieve stable long-run profitability, enforce Inspect guardrails (limits, logging, validation), and support analysis of tool usage across 2000-message episodes.【F:examples/vending_bench/source_excerpts.md-L5-L6】【F:examples/vending_bench/source_excerpts.md-L22-L28】
- **Non-Goals:** Automate real supplier communications or payment processing; external APIs may be stubbed as long as realism and determinism are preserved.

## Requirements
### Functional
- Advance the simulated clock per tool call (5 minutes to 5 hours), allow explicit day transitions, and cap episodes at 2000 turns to mirror the benchmark format.【F:examples/vending_bench/source_excerpts.md-L5-L6】【F:examples/vending_bench/source_excerpts.md-L10-L11】
- Enable research, supplier outreach, purchase ordering, and lead-time tracking through email and web-search tooling integrated with the environment state.【F:examples/vending_bench/source_excerpts.md-L10-L16】
- Maintain machine and storage inventories, cash balances, outstanding orders, demand parameters, and daily reports as first-class state elements.【F:examples/vending_bench/source_excerpts.md-L12-L16】
- Simulate customer demand using GPT-generated reference parameters, elasticity adjustments, seasonal/weather modifiers, variety penalties, and capped noisy draws.【F:examples/vending_bench/source_excerpts.md-L17-L19】
- Provide memory interfaces (scratchpad, key-value store, vector search) so the supervisor can persist notes, supplier data, and embeddings for retrieval.【F:examples/vending_bench/source_excerpts.md-L11-L12】【F:examples/vending_bench/source_excerpts.md-L23-L25】
- Delegate physical actions—restocking, price changes, cash collection—through a dedicated sub-agent surface with Inspect handoff semantics.【F:examples/vending_bench/source_excerpts.md-L18-L21】【F:examples/vending_bench/source_excerpts.md-L27-L28】

### Non-Functional
- Guarantee determinism via explicit seeds across demand noise, supplier timings, and any stochastic component.【F:examples/vending_bench/source_excerpts.md-L8-L9】
- Enforce Inspect validation and observability: Pydantic schemas, rejection of unknown fields, per-tool logging, and strict message/token ceilings for supervisor and sub-agent interactions.【F:examples/vending_bench/source_excerpts.md-L22-L28】
- Control context growth by codifying daily summaries, structured storage, and summarisation routines to keep working memory within budget.【F:examples/vending_bench/source_excerpts.md-L23-L25】
- Maintain solvency via cash buffers, fee handling, and elasticity-aware pricing heuristics to avoid bankrupt paths.【F:examples/vending_bench/source_excerpts.md-L15-L16】【F:examples/vending_bench/source_excerpts.md-L26-L26】

## System Architecture
- **Environment Simulator:** Python module owning core state (time, cash, inventories, orders, email, demand parameters) with deterministic transitions and scoring hooks.【F:examples/vending_bench/source_excerpts.md-L12-L16】
- **Supervisor Agent:** Inspect ReAct supervisor configured with environment and memory tools plus transfer_to_vending; responsible for planning, supplier negotiation, and financial decisions.【F:examples/vending_bench/source_excerpts.md-L7-L7】【F:examples/vending_bench/source_excerpts.md-L27-L28】 Machine stock visibility is restricted to the aggregated `check_machine_overview` wrapper while storage details route through `check_storage_inventory` to prevent leaking slot-level data across roles.
- **Physical Sub-Agent:** Inspect ReAct sub-agent instantiated with restock/set-price/cash tools, handoff limits, and quarantine filters to execute mechanical actions.【F:examples/vending_bench/source_excerpts.md-L18-L21】【F:examples/vending_bench/source_excerpts.md-L27-L27】
- **Memory Layer:** Scratchpad, key-value store, and vector database tools exposed via Inspect to manage long-term notes and embeddings.【F:examples/vending_bench/source_excerpts.md-L11-L12】【F:examples/vending_bench/source_excerpts.md-L23-L24】
- **Evaluation Harness:** Runner that invokes `run_agent` with wall-clock, message, and token limits, collecting metrics and tool telemetry for analysis.【F:examples/vending_bench/source_excerpts.md-L24-L28】

## Environment Simulation Design
### State Model
- Represent time as `(day, minute)` plus cash balances, storage/machine inventories, orders with lead times, email inbox/outbox, and cached demand parameters tied to seeds.【F:examples/vending_bench/source_excerpts.md-L12-L15】

### Daily Cycle
- Morning update delivers orders, applies demand, moves cash between machine and balance, charges the $2 fee, and emits a summary email.【F:examples/vending_bench/source_excerpts.md-L13-L16】
- Agent phase processes tool calls until `wait_for_next_day` or natural rollover; each call updates the clock per configured duration.【F:examples/vending_bench/source_excerpts.md-L10-L16】
- Order processing deducts cash immediately and schedules deterministic arrivals to align with vendor lead-time randomness.【F:examples/vending_bench/source_excerpts.md-L9-L13】

### Supplier Interactions
- Use `ai_web_search` to discover products and contacts, generate quotes with deterministic LLM calls, and attach replies to email inbox/outbox.【F:examples/vending_bench/source_excerpts.md-L10-L13】

### Demand Model
- Generate reference prices, elasticity, and base sales via a GPT-4o-backed provider (JSON schema) with deterministic fallback when API access is unavailable; compute demand via elasticity adjustments, seasonal/weather multipliers, variety penalties, and capped noisy draws.【F:examples/vending_bench/source_excerpts.md-L17-L19】

### Financial Management
- Track machine cash versus liquid balance, deduct daily fees, enforce buffers, and trigger price or ordering adjustments when thresholds fall below heuristics.【F:examples/vending_bench/source_excerpts.md-L15-L16】【F:examples/vending_bench/source_excerpts.md-L26-L26】

## Tool Surface
### Supervisor-Accessible Tools
- Expose email, search, inventory, financial, day-advance, and memory operations through Inspect tool wrappers with Pydantic request/response models and logging hooks.【F:examples/vending_bench/source_excerpts.md-L10-L16】【F:examples/vending_bench/source_excerpts.md-L22-L24】

### Memory Tools
- Implement scratchpad append/read/delete, key-value CRUD, and vector store operations with summarisation workflows to cap context growth.【F:examples/vending_bench/source_excerpts.md-L11-L12】【F:examples/vending_bench/source_excerpts.md-L23-L25】

### Sub-Agent Tools
- Provide `restock_machine`, `set_prices`, `collect_cash`, and `get_machine_inventory` primitives; enforce 8-24 message ceilings and quarantine filters per handoff.【F:examples/vending_bench/source_excerpts.md-L18-L21】【F:examples/vending_bench/source_excerpts.md-L27-L27】

### Validation and Observability
- Employ shared schema base classes, typed error objects, and Inspect logging to capture every tool call alongside limit utilisation for replay debugging.【F:examples/vending_bench/source_excerpts.md-L22-L28】

## Agent Stack
- Craft supervisor prompts that prioritise daily summaries, memory recall, supplier diligence, and financial discipline while delegating physical work via transfer_to_vending.【F:examples/vending_bench/source_excerpts.md-L18-L24】【F:examples/vending_bench/source_excerpts.md-L27-L27】
- Configure the sub-agent with task-specific prompt, physical tools, and deterministic limits to guarantee convergent execution.【F:examples/vending_bench/source_excerpts.md-L18-L21】【F:examples/vending_bench/source_excerpts.md-L27-L27】

## Memory Strategy
- Establish daily scratchpad entries, structured supplier/order registries, and email embeddings; periodically summarise older content to maintain searchable yet compact history.【F:examples/vending_bench/source_excerpts.md-L23-L25】

## Evaluation Plan
- Report net worth, units sold, tool counts, and cash runway per episode while enforcing the 2000-message cap and Inspect runtime limits.【F:examples/vending_bench/source_excerpts.md-L5-L6】【F:examples/vending_bench/source_excerpts.md-L26-L28】
- Store structured logs (metrics, tool spans) for regression tracking and ablation studies; integrate with existing Inspect log directories.

## Implementation Roadmap
1. **Phase 0 – Workspace Setup:** Organise `examples/vending_bench/` with module scaffolding, local configs, and environment documentation while importing `inspect_agents` as a library dependency.
2. **Phase 1 – Simulator Core:** Implement deterministic environment state, daily cycle handlers, demand model, and scoring utilities; add unit tests for time advancement and transactions.
3. **Phase 2 – Tooling & Memory:** Wrap environment actions as Inspect tools with validation/logging, integrate scratchpad/kv/vector utilities, and stub supplier data sources for deterministic replay.
4. **Phase 3 – Agents & Prompts:** Build supervisor and sub-agent prompts, configure handoff limits, and add prompt regression tests around restocking, pricing, and cash collection scenarios.
5. **Phase 4 – Evaluation Harness:** Assemble `examples/vending_bench/run.py` driver invoking `run_agent`, produce baseline configs, and capture sample transcripts/metrics for documentation.
6. **Phase 5 – Documentation & Ops:** Publish usage guide, troubleshooting tips, and runbooks for limit breaches, supplier stubs, and memory grooming.
7. **Phase 6 – Mirror & Release Ops:** Stand up a dedicated repository mirror with release workflows, documentation sync, and issue tracking for long-term maintenance.


## Mirror Repository Blueprint
- **Proposed name:** `inspect-vending-bench-mirror`; mirrors `examples/vending_bench/` from this workspace.
- **Directory skeleton:** top-level `README.md`, `mirror/` (synced code), `ci/` for automation, and `release-notes/` for changelog snapshots.
- **README outline:** overview, sync process, setup instructions, release policy, maintenance contacts, and links back to the upstream repository.
- **CI workflow:** GitHub Actions pipeline (`ci/sync.yml`) that pulls from upstream, runs smoke tests (`uv run pytest -q tests/unit/vending_bench`), validates docs, and opens sync PRs when diffs exist.
- **Release tags:** semantic versions `mirror-v<major>.<minor>.<patch>` generated after sync PR merges; tags reference corresponding upstream commit SHA.
- **Workspace integration:** add a `tools/mirror_sync.py` helper in this repo to package artifacts and push to the mirror via the CI workflow; document usage in `examples/vending_bench/README.md`.
- **Issue management:** enable GitHub Discussions and Issues in the mirror to capture external feedback without polluting the upstream repo.
- **Security & governance:** require CODEOWNERS approvals on the mirror, and schedule quarterly review of automation credentials.

## Risks and Mitigations
- **Long-horizon drift:** Agents may forget prior orders or cash targets; mitigate with enforced memory checks and daily scratchpad templates.【F:examples/vending_bench/source_excerpts.md-L23-L26】
- **Tool misuse:** Incorrect parameters or runaway delegations could break sessions; mitigate via Pydantic validation, typed errors, and strict handoff limits.【F:examples/vending_bench/source_excerpts.md-L22-L28】
- **Economic collapse:** Aggressive ordering or price errors can bankrupt the agent; mitigate with buffer heuristics and elasticity-aware pricing.【F:examples/vending_bench/source_excerpts.md-L26-L26】

## Open Questions
- What fidelity is required for supplier catalogs (real APIs vs deterministic fixtures) to balance realism and reproducibility?
- How should we seed demand parameter generation to permit scenario variations without breaking comparability?
- Do we need additional analytics (e.g., seasonality diagnostics) in the evaluation harness beyond the core metrics?
- What governance model and release cadence should the mirror repository follow once public?

## Feature Backlog
- **Feature: Simulator Core Completion** – Implement the deterministic environment module (state, demand, suppliers, cash flow) and land accompanying unit tests.
- **Feature: Tooling & Memory Integration** – Expose environment actions as Inspect tools, finalise memory surfaces, and validate schemas via smoke runs.
- **Feature: Agent Harness Assembly** – Ship supervisor/sub-agent prompts with a runnable evaluation harness that enforces Inspect limits and captures metrics.
- **Feature: Mirror Automation Pipeline** – Wire up CI sync workflow, release tagging, and documentation handoff for the external mirror repository.
