# Exploration Examples — Implementation Prompts (Hand‑offs for SWE)

This page contains complete, copy‑pasteable prompts for implementing the examples‑only exploration flow under `examples/`. Each prompt includes Context & Motivation, Implementation Guidance, Scope, and Success Criteria.

Note: Keep all code under `examples/` and `tests/examples_exploration/`. Do not modify `src/inspect_agents/` in this pass.

---

## 1) Exploration Planner (Heuristics + Breadth/Stop)

Context & Motivation
- Purpose: Add a deterministic exploration planner that expands a user prompt into a small, diverse set of web queries with bounded breadth/depth and clear stop rules. This provides “plan before act” behavior similar to Deep Research while controlling cost/time.
- Problem/Impact: Current examples rely on ad‑hoc researcher prompts. A planner creates structured exploration tasks up front (query variants, target domains, per‑step depth), increasing findability and repeatability.
- Constraints: Implement in examples only; no changes under `src/`. Keep pure‑Python, deterministic (seedable), and runnable offline for unit tests.

Implementation Guidance
- Add file: `examples/inspect/exploration/planner.py`.
- Examine example patterns: `examples/tasks/research_task.py` (agent composition); grep for `build_supervisor`, `build_subagents`, `standard_tools`, `research_task`.
- API (use Pydantic models for clarity):
  - `class ExplorationConfig(BaseModel): breadth:int=3; depth:int=2; seed:int=0; convergence_delta:float=0.05; max_queries:int=12; synonym_expansion:bool=True; site_hints:list[str]|None=None`
  - `class QuerySpec(BaseModel): query:str; depth:int; tags:list[str]=[]; target_domains:list[str]=[]`
  - `def classify_prompt(prompt:str)->str` → "fresh"|"evergreen"
  - `def generate_seed_queries(prompt:str, cfg:ExplorationConfig)->list[QuerySpec]`
  - `def expand_frontier(seeds:list[QuerySpec], cfg:ExplorationConfig)->list[QuerySpec]` (BFS up to breadth/depth, dedupe)
  - `def plan(prompt:str, cfg:ExplorationConfig)->list[QuerySpec]`
- Heuristics: detect temporal tokens (years, "today", "latest"); add operator variants (`intitle:`, `site:` from `cfg.site_hints`); include small synonym list (stdlib only). Ensure domain diversity; normalize and dedupe queries.
- Determinism: use `random.Random(cfg.seed)` for any permutations.

Scope Definition
- Implement only planner functions and dataclasses in `examples/inspect/exploration/planner.py`.
- No network I/O; no external NLP libs.
- Expose `plan()` as the entry point.

Success Criteria
- REPL: `from examples.inspect.exploration.planner import plan, ExplorationConfig as C; plan("Research X", C())` returns ≤ `max_queries` items; depths ≤ cfg.depth.
- Unit tests (separate prompt) can seed cfg for stable counts/order.
- Minimal latency; stdlib‑only.

---

## 2) Scoring Module (Authority/Recency/Topical/Citation)

Context & Motivation
- Purpose: Prioritize reputable, fresh, and on‑topic sources with citations to improve report quality.
- Problem/Impact: Without scoring, the researcher may over‑index on the first results; scoring promotes authority/recency and penalizes duplicates.
- Constraints: examples only; no external embeddings.

Implementation Guidance
- Add file: `examples/inspect/exploration/scoring.py`.
- Review `src/inspect_agents/tools.py` to understand web_search fields (don’t modify it). Grep: `standard_tools`, `web_search`.
- Data models:
  - `class Result(BaseModel): url:str; title:str; snippet:str; published_at:datetime|None=None`
  - `class ScoringConfig(BaseModel): w_authority:float=0.35; w_recency:0.25; w_topic:0.3; w_citation:0.1; domain_whitelist:list[str]=["arxiv.org","*.gov","*.edu"]; domain_blacklist:list[str]=[]; duplicate_title_jaccard:float=0.9`
- Functions:
  - `normalize_domain(url)->str`, `domain_authority(domain)->float`
  - `recency_weight(published_at, now)->float` (half‑life ~ 365 days)
  - `topical_similarity(query, text)->float` (token overlap/Jaccard)
  - `citation_present(snippet|title)->float` (patterns: doi, arXiv, [n])
  - `dedupe_penalty(title_a, title_b)->float`
  - `score(query, result, cfg, now)->float`, `rerank(query, results, cfg, now)->list[Result]`

Scope Definition
- Implement standalone scoring utilities; no calls to web_search.
- Deterministic code, stdlib only.

Success Criteria
- Mock results reorder as expected (whitelist/recency favored, dupes penalized).
- Unit tests verify stability and thresholds.

---

## 3) Planner Tool (Inspect Tool Wrapper)

Context & Motivation
- Purpose: Expose the planner to the supervisor as an Inspect tool that returns a JSON plan; enables auditability and policy knobs.
- Constraints: examples‑only; JSON‑serializable output.

Implementation Guidance
- Add file: `examples/inspect/exploration/planner_tool.py`.
- Follow tool factory pattern from `src/inspect_agents/tools.py` (see `write_todos`) without modifying it. Grep: `from inspect_ai.tool._tool import tool`.
- Implement:
  ```python
  from inspect_ai.tool._tool import tool
  from .planner import plan, ExplorationConfig

  @tool
  def planner_tool():
      async def execute(prompt: str, config: dict | None = None) -> dict:
          cfg = ExplorationConfig.model_validate(config or {})
          queries = plan(prompt, cfg)
          return {"queries": [q.model_dump() for q in queries], "breadth": cfg.breadth, "depth": cfg.depth}
      return execute
  ```
- Parameter schema: `prompt` (str), `config` (object).

Scope Definition
- Only add this tool; keep imports inside factory if heavy.

Success Criteria
- Tool returns JSON with ≤ `max_queries`; elements include `query`, `depth`, `tags`.
- Visible in supervisor tool list when added by the runner/task.

---

## 4) Runner Wiring (Supervisor + Sub‑agents + Planner)

Context & Motivation
- Purpose: Provide a runnable example that orchestrates planner → research‑agent → critique‑agent; writes `plan.json`, `question.txt`, `final_report.md`.

Implementation Guidance
- Add file: `examples/inspect/exploration/runner.py`.
- Reference: `examples/tasks/research_task.py` for sub‑agent structure.
- Steps:
  - Resolve model via `inspect_agents.model.resolve_model()`.
  - Tools: built‑ins `write_todos, update_todo_status, write_file, read_file, ls, edit_file` + `standard_tools()` + `planner_tool()`.
  - Sub‑agents:
    - research‑agent: reads `plan.json`, executes top queries, composes `final_report.md` with citations.
    - critique‑agent: reads `final_report.md`, suggests improvements.
  - Supervisor: prompts to call `planner_tool`, persist `plan.json`, write `question.txt`, handoff to research‑agent; after report, handoff to critique‑agent.
  - Approvals: use `approval_preset("ci")` in example; do not enable parallel kill‑switch via env.
- CLI: `uv run python -m examples.inspect.exploration.runner --config examples/configs/research/exploration.yaml "Investigate <topic>"`

Scope Definition
- No changes to library; wiring lives in examples.

Success Criteria
- Transcript shows planner_tool → research‑agent → critique‑agent handoffs.
- Artifacts `plan.json`, `question.txt`, `final_report.md` appear in the in‑memory FS.

---

## 5) Inspect Task Wrapper (exploration_task)

Context & Motivation
- Purpose: Expose the exploration flow via `inspect eval` for reproducible CLI runs.

Implementation Guidance
- Add file: `examples/tasks/exploration_task.py`.
- Follow `@task` pattern from `examples/tasks/research_task.py`.
- Signature:
  ```python
  @task
  def exploration_task(prompt: str = "Write a short overview of Inspect‑AI",
                       attempts: int = 3,
                       policy_config: str = "examples/configs/research/exploration.yaml",
                       enable_web_search: bool = False):
      ...
  ```
- If `enable_web_search`, set `INSPECT_ENABLE_WEB_SEARCH=1`.
- Build tools and sub‑agents as in runner; load YAML and pass `policy` dict to planner_tool.

Scope Definition
- Add a new task only; do not modify existing tasks.

Success Criteria
- `inspect eval` run shows planner_tool invocation; with search enabled, produces a cited report and critique.

---

## 6) Policy YAML (Tunables and Priors)

Context & Motivation
- Purpose: Centralize breadth/depth/weights/priors in YAML to iterate without code changes.

Implementation Guidance
- Add file: `examples/configs/research/exploration.yaml` with sections `policy`, `scoring`, `supervisor` (see How‑To page for example schema).
- Runner/task should load YAML and hand `policy` block to planner_tool as a dict.

Scope Definition
- YAML under examples only; no schema library required.

Success Criteria
- Changing YAML breadth/depth deterministically affects planner output size.

---

## 7) Tests for Examples (Planner, Scoring, Integration)

Context & Motivation
- Purpose: Provide deterministic coverage and a no‑network integration check.

Implementation Guidance
- Add test files:
  - `tests/examples_exploration/test_planner_heuristics.py`
  - `tests/examples_exploration/test_scoring.py`
  - `tests/examples_exploration/test_integration_offline.py`
- Planner tests: seed config (e.g., `seed=42`); assert counts, depth bounds, diversity.
- Scoring tests: mock results with dates/domains; assert order by score.
- Integration (offline): without `INSPECT_ENABLE_WEB_SEARCH`, run minimal supervisor flow that calls `planner_tool` and writes `plan.json` + `question.txt`; assert JSON structure and bounds.
- Command: `CI=1 NO_NETWORK=1 PYTHONPATH=src:external/inspect_ai uv run pytest -q tests/examples_exploration`

Scope Definition
- Tests live under `tests/examples_exploration`; do not modify core tests.

Success Criteria
- All new tests pass locally with `NO_NETWORK=1`; behavior deterministic under fixed seed.
