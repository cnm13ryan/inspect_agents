---
title: Simple Agent Architecture (Inspect‑AI)
status: Accepted
date: 2025-09-05
---

Context
The project aims to build reproducible, sandboxed agent benchmarks and evals rather than general LLM apps. While ecosystems like LangChain/LangGraph and DeepAgents provide agent frameworks, Inspect‑AI offers a better fit here: first‑class tool approvals, transcript/logging, sandboxable tools, and deterministic testability. We model a minimal, composable “simple agent architecture” consisting of: Environment, Main Agent, Sub‑Agent, and Memory + Tooling.

Motivation & Origins
- Vending‑Bench identified a straightforward architecture (env ↔ main agent ↔ tools/memory + optional sub‑agent), which we adapt in Inspect‑AI form to focus on evaluation and capabilities tracking rather than product features (see: Vending‑Bench paper, arXiv: 2502.15840).
- Similar patterns were observed in systems like Deep Research and Claude Code; see Harrison Chase’s blog on Deep Agents and the langchain‑ai/deepagents skeleton.

Design
- Agents: Use Inspect’s `react()` agent for both main and sub‑agent, with the default `submit` termination semantics.
- Handoff: Use Inspect’s `handoff()` to expose the sub‑agent as a `transfer_to_<name>` tool for delegation.
- Memory Tools: Small key‑value memory with `write_memory`, `read_memory`, `list_memory` tools. Deterministic and easy to stub.
- Environment Tools: `env_observe` and `env_act(action)` bound to a simple in‑memory textual environment.
- Orchestration: Thin wrapper over Inspect’s `agent.run()` to preserve transcripts, limits, and logs.
- Approvals & Policies: Prefer repo presets that enforce first‑handoff exclusivity and an optional parallel kill‑switch; adopt Inspect approval plumbing (`init_tool_approval`) when activations are requested by the caller.

Implementation (paths)
- Example only: `examples/demos/` (demo tools + runner)
- Library code lives under `src/inspect_agents/` and should be used directly
  (e.g., `build_supervisor`, `build_iterative_agent`, approvals presets, tools).
- Tests: unchanged; demo is opt‑in and not imported by the test suite.

Operational Notes
- Run with `approval_preset("dev")` for safe local iteration; CI may use a permissive chain.
- Keep tool sets small and deterministic in benchmarks; prefer explicit env flags for heavy tools.

Future Work
- Pluggable persistent memory and retrieval.
- Richer environment simulators (file/HTTP backed) and standard env adapters.
- Additional policies (rate limits, per‑agent quotas) and telemetry lenses.
