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
