Scoring Demo (Authority/Recency/Topical/Citation)

- Purpose: Offline-friendly reranker that scores results by domain authority, recency, topical overlap, and citation hints.
- Location: `examples/inspect/exploration/scoring.py` (library) and `demo_scoring.py` (CLI demo).

Quick Start
- Run demo with deterministic now:
  - `python examples/inspect/exploration/demo_scoring.py --query "mars exploration" --topk 5 --now 2025-01-01`
  - Output formats: JSON (default), CSV, TSV via `--output {json|csv|tsv}`.
    - CSV example: `... --output csv > scores.csv`
    - TSV example: `... --output tsv > scores.tsv`
- Use custom JSON input (list of objects):
  - `python examples/inspect/exploration/demo_scoring.py --query q --json path/to/results.json --now 2025-01-01`
  - JSON item fields: `url`, `title`, `snippet`, `published_at` (ISO 8601: `YYYY-MM-DD` or full ISO). Missing/invalid dates treated as unknown.

Model & Weights
- Components:
  - Authority: domain prior (whitelist +0.5, blacklist −0.5, `.gov`/`.edu` +0.2).
  - Recency: exponential decay `0.5 ** (Δdays / 365)`. Unknown → 0.0.
  - Topic: Jaccard overlap on lowercased alnum tokens of `query` vs `title+snippet`.
  - Citation: 1.0 if DOI present; 0.8 if arXiv id/URL; 0.5 if bracketed numeric `[n]`; else 0.0.
- Default weights (`ScoringConfig`): `w_authority=0.35`, `w_recency=0.25`, `w_topic=0.30`, `w_citation=0.10`.
- Duplicate handling: near-duplicate titles (Jaccard ≥ `duplicate_title_jaccard=0.90`) get a small negative penalty applied to later items; sorting is stable.
- Weight overrides (demo only): `--w-authority`, `--w-recency`, `--w-topic`, `--w-citation` to tune at runtime.

Library Usage (Python)
```python
from datetime import datetime, timezone
from examples.inspect.exploration.scoring import Result, ScoringConfig, rerank_with_scores

cfg = ScoringConfig()
now = datetime.now(tz=timezone.utc)
results = [
    Result(url="https://arxiv.org/abs/2405.01234", title="Mars study", snippet="doi:10.1/x", published_at=now),
]
ranked = rerank_with_scores("mars exploration", results, cfg, now)
for sr in ranked:
    print(sr.result.url, sr.score, sr.components)
```

Testing
- Run only scoring tests: `uv run pytest -q tests/unit/examples/test_scoring_unit.py`
- What’s covered: domain priors (.gov/.edu, whitelist/blacklist), recency half-life (~365 days), Jaccard properties, rerank ordering (gov/arXiv > blog), duplicate-title penalty, and explainability (`score_components`).

Notes
- Deterministic and offline-friendly; no web calls or embeddings.
- Domain whitelist defaults: `arxiv.org`, `*.gov`, `*.edu`. Configure via `ScoringConfig.domain_*`.

YAML Policy & Runner Overrides
- Config path: `examples/configs/research/exploration.yaml`. Sections:
  - `policy`: Planner knobs used by `planner_tool` (via its loader) — `max_queries`, `breadth`, `depth`, optional `seed`, `convergence_delta`, `synonym_expansion`, `site_hints`, and `tags`.
  - `scoring`: Component weights and domain priors for future wiring; currently loaded by the runner and available to sub‑agents.
  - `supervisor`: Runner‑only overrides for `attempts` and role prompts.
- Precedence
  - Attempts: `supervisor.attempts` (YAML) overrides the CLI `--attempts` flag if present.
  - Prompts: If `supervisor.prompts` defines `supervisor|research|critique`, the runner applies them as:
    - Supervisor: YAML text is prepended to the runner’s standard instructions (keeps safety/IO guidance intact).
    - Research/Critique sub‑agents: YAML text fully replaces the default role prompts.
- Visibility (auditability)
  - When a YAML config is provided, the runner includes a “Planner config (JSON): …” footer in the supervisor prompt containing the exact JSON passed to `planner_tool`. This makes policy choices explicit in transcripts.
- Usage (runner)
  - `uv run python -m examples.inspect.exploration.runner --config examples/configs/research/exploration.yaml "Investigate <topic>"`
  - With no `--config`, the runner uses in‑code defaults and omits the planner config footer.

Planner Policy Keys (defaults)
- Source of defaults: code-level `ExplorationConfig` in `examples/inspect/exploration/planner.py`. The example YAML (`examples/configs/research/exploration.yaml`) may set different values (e.g., `max_queries: 6`).

| Key | Type | Default | Description |
|---|---|---:|---|
| `breadth` | int | 3 | Number of seed/frontier variants per layer. |
| `depth` | int | 2 | Max BFS expansion depth (seed is depth 0). |
| `max_queries` | int | 12 | Global cap on returned `QuerySpec` items. |
| `seed` | int | 0 | RNG seed for deterministic shuffles. |
| `convergence_delta` | float | 0.05 | Early-stop threshold on marginal gain between layers. |
| `synonym_expansion` | bool | true | Enable cheap synonym-based variants. |
| `site_hints` | list[str] or null | null | Preferred domains; used for `site:` variants and diversity. |

Reference
- Example config file: `examples/configs/research/exploration.yaml` (policy, scoring, supervisor sections). Adjust `policy` values there to change planner behavior without code changes.
