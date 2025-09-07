from __future__ import annotations

from datetime import UTC, datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_scoring() -> object:
    repo_root = Path(__file__).resolve().parents[3]
    mod_path = repo_root / "examples" / "inspect" / "exploration" / "scoring.py"
    assert mod_path.exists(), f"Missing module at {mod_path}"
    spec = spec_from_file_location("examples_scoring", str(mod_path))
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    return mod


def test_scoring_domain_recency_and_duplicates() -> None:
    s = _load_scoring()
    # Resolve postponed evaluation of typing annotations under Pydantic (best-effort)
    try:
        s.ScoringConfig.model_rebuild()
        s.Result.model_rebuild()
    except Exception:
        pass

    now = datetime(2025, 9, 7, tzinfo=UTC)

    class Cfg:
        w_authority = 0.35
        w_recency = 0.25
        w_topic = 0.30
        w_citation = 0.10
        domain_whitelist = ["arxiv.org", "*.gov", "*.edu"]
        domain_blacklist = []
        duplicate_title_jaccard = 0.90

    cfg = Cfg()

    # Lightweight Result shim to avoid Pydantic import semantics in sandbox
    class Result:
        def __init__(self, url: str, title: str, snippet: str, published_at=None):
            self.url = url
            self.title = title
            self.snippet = snippet
            self.published_at = published_at

    # Mock results across domains/dates, some exact duplicate titles to trigger penalty
    base_title = "Large Language Models for Search"
    results = [
        Result(
            url="https://arxiv.org/abs/2401.01234",
            title=base_title,
            snippet="We present a study with DOI:10.1000/xyz123",
            published_at=now - timedelta(days=30),
        ),  # arxiv (whitelist + citation)
        Result(
            url="https://example.org/blog/llm-search-1",
            title="LLM search insights",
            snippet="Part 1",
            published_at=now - timedelta(days=100),
        ),  # neutral domain
        Result(
            url="https://example.org/blog/llm-search-2",
            title="LLM search insights",  # exact duplicate title later in list
            snippet="Part 2",
            published_at=now - timedelta(days=99),  # slightly newer
        ),  # should be penalized below the first one despite slightly newer date
    ]

    # Whitelist authority should make arxiv/nasa.gov generally stronger than example.org
    a_score = s.score("llm search", results[0], cfg, now)
    e1_score = s.score("llm search", results[1], cfg, now)
    s.score("llm search", results[2], cfg, now)
    assert a_score > e1_score  # whitelist domain beats neutral

    # Newer item should rank higher than older, holding others roughly constant
    newer = Result(url="https://foo.edu/x", title="Survey", snippet="", published_at=now - timedelta(days=5))
    older = Result(url="https://foo.edu/x", title="Survey", snippet="", published_at=now - timedelta(days=500))
    assert s.score("survey", newer, cfg, now) > s.score("survey", older, cfg, now)

    # Rerank stability and duplicate penalty: later near-duplicate drops
    order1 = s.rerank("llm search", list(results), cfg, now)
    order2 = s.rerank("llm search", list(results), cfg, now)
    assert [r.url for r in order1] == [r.url for r in order2]

    # Duplicate penalty check: later duplicate (example.org #2) should appear after the earlier one
    urls = [r.url for r in order1]
    assert urls.index("https://example.org/blog/llm-search-1") < urls.index("https://example.org/blog/llm-search-2")
