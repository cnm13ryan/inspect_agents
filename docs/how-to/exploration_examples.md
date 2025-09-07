# Exploration Examples — Planner, Scoring, Runner (Inspect‑AI)

This page documents an examples‑only implementation that brings planning and bounded exploration to the research demo without changing the library under `src/inspect_agents/`.

Goal
- Provide a small, auditable “plan → execute → critique” flow under `examples/` that mimics Deep‑Research‑style behavior while remaining flag‑gated and testable offline.

What You Get
- Planner (heuristics) that expands a prompt into diverse queries with breadth/depth caps.
- Optional scoring module (authority, recency, topicality, citation bonus).
- Planner tool that returns a JSON plan to the supervisor.
- Runner and Inspect task wiring (supervisor → research‑agent → critique‑agent).

Repository Layout (planned)
- `examples/inspect/exploration/planner.py` — pure functions for prompt classification, seed queries, frontier expansion, stop rules.
- `examples/inspect/exploration/scoring.py` — optional utilities to score/rerank results.
- `examples/inspect/exploration/planner_tool.py` — Inspect tool wrapper around `planner.plan()`.
- `examples/inspect/exploration/runner.py` — builds supervisor + sub‑agents; persists `plan.json`, `question.txt`, `final_report.md`.
- `examples/tasks/exploration_task.py` — Inspect task wrapper for `inspect eval`.
- `examples/configs/research/exploration.yaml` — tunables: breadth/depth/weights/priors.
- `tests/examples_exploration/` — deterministic tests for planner, scoring, and offline integration.

Environment & Flags
- Enable search: `INSPECT_ENABLE_WEB_SEARCH=1` and set either `TAVILY_API_KEY`, or `GOOGLE_CSE_ID` + `GOOGLE_CSE_API_KEY`.
- Long‑horizon defaults (already added to `.env`):
  - `INSPECT_ITERATIVE_TIME_LIMIT=7200`, `INSPECT_ITERATIVE_MAX_STEPS=200`
  - `INSPECT_PRUNE_AFTER_MESSAGES=300`, `INSPECT_PRUNE_KEEP_LAST=80`
  - `INSPECT_PRODUCTIVE_TIME=1`, `INSPECT_MAX_TOOL_OUTPUT=65536`

YAML (policy + scoring)
```yaml
policy:
  name: exploration_v0
  breadth: 3
  depth: 2
  max_queries: 12
  convergence_delta: 0.05
  synonym_expansion: true
  site_hints: ["arxiv.org", "doi.org", "*.gov", "*.edu"]

scoring:
  w_authority: 0.35
  w_recency: 0.25
  w_topic: 0.30
  w_citation: 0.10
  domain_whitelist: ["arxiv.org","*.gov","*.edu"]
  domain_blacklist: []

supervisor:
  attempts: 3
  prompts:
    supervisor: "You are the orchestrator..."
    research:   "You are a dedicated researcher..."
    critique:   "You are a detailed editor..."
```

How to Run (task)
```bash
INSPECT_ENABLE_WEB_SEARCH=1 TAVILY_API_KEY=YOUR_KEY \
uv run inspect eval examples/tasks/exploration_task.py \
  -T policy_config=examples/configs/research/exploration.yaml \
  -T prompt="Investigate <topic>; include sources" -T attempts=5
```

Planner Policy Keys (defaults)
- Defaults come from the examples code (`ExplorationConfig` in `examples/inspect/exploration/planner.py`). The example YAML at `examples/configs/research/exploration.yaml` may set different values for convenience.

| Key | Type | Default | Description |
|---|---|---:|---|
| `breadth` | int | 3 | Number of seed/frontier variants per layer. |
| `depth` | int | 2 | Max BFS expansion depth (seed is depth 0). |
| `max_queries` | int | 12 | Global cap on returned `QuerySpec` items. |
| `seed` | int | 0 | RNG seed for deterministic shuffles. |
| `convergence_delta` | float | 0.05 | Early-stop threshold on marginal gain between layers. |
| `synonym_expansion` | bool | true | Enable cheap synonym-based variants. |
| `site_hints` | list[str] or null | null | Preferred domains; used for `site:` variants and diversity. |

Reference: see `examples/configs/research/exploration.yaml` (policy, scoring, supervisor sections).

How to Run (python runner)
```bash
uv run python -m examples.inspect.exploration.runner \
  --config examples/configs/research/exploration.yaml \
  "Investigate <topic>"
```

Note: When `--config` is provided, the supervisor prompt includes a “Planner config (JSON): …” footer containing the exact planner policy JSON for auditability.

Outputs & Artifacts
- `plan.json` — queries with depth/tags; used by research‑agent.
- `question.txt` — original user question.
- `final_report.md` — structured, cited report; critique‑agent edits.

Approvals & Tool Policy
- Examples use `approval_preset("ci")` (permissive) to allow planner + search tools.
- Handoff exclusivity remains enforced; parallel kill‑switch is not enabled by default.

Testing (examples only)
```bash
CI=1 NO_NETWORK=1 PYTHONPATH=src:external/inspect_ai \
uv run pytest -q tests/examples_exploration
```

Promotion Path (optional)
- Keep logic under `examples/` while iterating; when stable, extract core pieces to `src/inspect_agents/policy/...` behind an opt‑in flag.
