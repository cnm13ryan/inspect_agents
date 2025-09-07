"""Demo: authority/recency/topic/citation scoring and rerank.

Usage
  python examples/inspect/exploration/demo_scoring.py \
      --query "mars exploration" --topk 5 --now 2025-01-01

Optionally supply JSON input with a list of results:
  [
    {"url": "https://arxiv.org/abs/2405.01234", "title": "A", "snippet": "...", "published_at": "2025-05-10"}
  ]

  python examples/inspect/exploration/demo_scoring.py --query q --json path/to/results.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any
import sys
from pathlib import Path
import csv

# Ensure repo root on path so we can import examples.* when invoked as a script
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.inspect.exploration.scoring import (
    Result,
    ScoringConfig,
    rerank_with_scores,
)


def _parse_dt(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        # Accept YYYY-MM-DD or full ISO; assume naive is UTC
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _load_results_from_json(path: str) -> list[Result]:
    data = json.loads(open(path, "r", encoding="utf-8").read())
    out: list[Result] = []
    for item in data:
        out.append(
            Result(
                url=item.get("url", ""),
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                published_at=_parse_dt(item.get("published_at")),
            )
        )
    return out


def _mock_results(now: datetime) -> list[Result]:
    # Use relative dates from provided 'now' for determinism when --now is used
    return [
        Result(
            url="http://randomblog.net/mars",
            title="Thoughts on Mars",
            snippet="a personal blog post",
            published_at=now.replace(tzinfo=timezone.utc) if now.tzinfo else now,
        ),
        Result(
            url="https://www.nasa.gov/news",
            title="New NASA study on Mars",
            snippet="details (doi:10.1234/5678)",
            published_at=(now.replace(tzinfo=timezone.utc) if now.tzinfo else now),
        ),
        Result(
            url="https://arxiv.org/abs/2405.01234",
            title="Learning for Mars Rovers",
            snippet="ArXiv:2405.01234 shows results",
            published_at=(now.replace(tzinfo=timezone.utc) if now.tzinfo else now),
        ),
        Result(
            url="https://cs.stanford.edu/mars",
            title="Mars terrain mapping",
            snippet="comparison with prior work [12]",
            published_at=None,
        ),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True, help="search/query text")
    ap.add_argument("--json", help="path to JSON list of {url,title,snippet,published_at}")
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--now", help="YYYY-MM-DD override for 'now' (UTC)")
    ap.add_argument("--output", choices=["json", "csv", "tsv"], default="json", help="output format (default: json)")

    # Weight overrides for rapid tuning
    g = ap.add_argument_group("weights", "Override ScoringConfig component weights")
    g.add_argument("--w-authority", dest="w_authority", type=float, help="weight for domain authority (default 0.35)")
    g.add_argument("--w-recency", dest="w_recency", type=float, help="weight for recency (default 0.25)")
    g.add_argument("--w-topic", dest="w_topic", type=float, help="weight for topical similarity (default 0.30)")
    g.add_argument("--w-citation", dest="w_citation", type=float, help="weight for citation signal (default 0.10)")
    args = ap.parse_args()

    if args.now:
        now = datetime.fromisoformat(args.now)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)
    else:
        now = datetime.now(tz=timezone.utc)

    results = _load_results_from_json(args.json) if args.json else _mock_results(now)
    # Build config with optional weight overrides
    cfg_updates = {}
    for k in ("w_authority", "w_recency", "w_topic", "w_citation"):
        v = getattr(args, k, None)
        if v is not None:
            cfg_updates[k] = float(v)
    cfg = ScoringConfig().model_copy(update=cfg_updates)
    ranked = rerank_with_scores(args.query, results, cfg, now)

    topk = ranked[: args.topk]
    if args.output == "json":
        payload = [
            {
                "rank": i + 1,
                "url": r.result.url,
                "title": r.result.title,
                "score": round(r.score, 6),
                "components": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.components.items()},
            }
            for i, r in enumerate(topk)
        ]
        print(json.dumps(payload, indent=2))
    else:
        # Flatten to tabular rows for spreadsheet analysis
        headers = [
            "rank",
            "url",
            "title",
            "score",
            "authority",
            "recency",
            "topic",
            "citation",
            "weighted_sum",
            "duplicate_penalty",
        ]
        delim = "," if args.output == "csv" else "\t"
        writer = csv.writer(sys.stdout, delimiter=delim, lineterminator="\n")
        writer.writerow(headers)
        for i, r in enumerate(topk):
            comps = r.components
            row = [
                i + 1,
                r.result.url,
                r.result.title,
                round(float(r.score), 6),
                round(float(comps.get("authority", 0.0)), 6),
                round(float(comps.get("recency", 0.0)), 6),
                round(float(comps.get("topic", 0.0)), 6),
                round(float(comps.get("citation", 0.0)), 6),
                round(float(comps.get("weighted_sum", 0.0)), 6),
                round(float(comps.get("duplicate_penalty", 0.0)), 6),
            ]
            writer.writerow(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
