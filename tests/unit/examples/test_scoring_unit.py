import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure repo root is on path so we can import examples.* for tests
ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import after path modification to avoid E402
from examples.inspect.exploration.scoring import (  # noqa: E402
    Result,
    ScoringConfig,
    citation_present,
    domain_authority,
    normalize_domain,
    recency_weight,
    rerank,
    rerank_with_scores,
    score,
    score_components,
    topical_similarity,
)


def test_normalize_domain_variants():
    assert normalize_domain("https://WWW.Example.com:8080/path") == "example.com"
    assert normalize_domain("example.com/path") == "example.com"
    assert normalize_domain("http://user:pass@sub.domain.edu") == "sub.domain.edu"


def test_domain_authority_priors():
    cfg = ScoringConfig()
    assert domain_authority("arxiv.org", cfg) >= 0.5
    assert domain_authority("nasa.gov", cfg) >= 0.7  # whitelist + TLD
    cfg2 = ScoringConfig(domain_whitelist=[], domain_blacklist=["spam.click"])
    assert domain_authority("spam.click", cfg2) <= -0.5
    # wildcard applies to subdomains
    assert domain_authority("cs.stanford.edu", cfg) >= 0.7


def test_recency_weight_decay_and_neutral_none():
    now = datetime(2025, 1, 1)
    assert recency_weight(now, now) == 1.0
    one_year_ago = now - timedelta(days=365)
    assert 0.49 <= recency_weight(one_year_ago, now) <= 0.51
    two_years_ago = now - timedelta(days=730)
    w = recency_weight(two_years_ago, now)
    assert 0.24 <= w <= 0.26
    assert recency_weight(None, now) == 0.0


def test_topical_similarity_jaccard_properties():
    a = "Hello, World!"
    b = "hello world"
    c = "foo bar baz"
    assert topical_similarity(a, b) == 1.0
    assert topical_similarity(a, c) == 0.0


def test_citation_present_heuristics():
    assert citation_present(title="", snippet="doi:10.1145/1234/abcd") == 1.0
    assert citation_present(title="arXiv: 2405.01234", snippet="") == 0.8
    assert citation_present(title="Study [12] compares", snippet="") == 0.5
    assert citation_present(title="No cites here", snippet="just text") == 0.0


def test_rerank_government_and_arxiv_outrank_blog():
    cfg = ScoringConfig()
    now = datetime(2025, 1, 1)

    blog = Result(
        url="http://randomblog.net/mars",
        title="Thoughts on Mars",
        snippet="a personal blog post",
        published_at=now - timedelta(days=200),
    )
    nasa = Result(
        url="https://www.nasa.gov/news",
        title="New NASA study on Mars",
        snippet="details (doi:10.1234/5678)",
        published_at=now - timedelta(days=400),
    )
    arxiv = Result(
        url="https://arxiv.org/abs/2405.01234",
        title="Learning for Mars Rovers",
        snippet="ArXiv:2405.01234 shows results",
        published_at=now - timedelta(days=30),
    )

    ranked = rerank("mars exploration", [blog, nasa, arxiv], cfg, now)
    # The blog should be last; top two are gov/arxiv in any order
    assert ranked[-1].url == blog.url
    assert {ranked[0].url, ranked[1].url} == {nasa.url, arxiv.url}


def test_duplicate_title_penalty_orders_later_duplicate_after_first():
    cfg = ScoringConfig(duplicate_title_jaccard=0.9)
    now = datetime(2025, 1, 1)
    r1 = Result(url="https://site/a", title="Deep Learning Basics", snippet="", published_at=None)
    r2 = Result(url="https://site/b", title="Deep   Learning  Basics!!!", snippet="", published_at=None)
    ranked = rerank("deep learning", [r2, r1], cfg, now)
    # r1 and r2 are near-identical titles; the one that appears first should win
    assert ranked[0].title == r2.title
    assert ranked[1].title == r1.title


def test_score_components_sum_matches_score_function():
    cfg = ScoringConfig()
    now = datetime(2025, 1, 1)
    r = Result(url="https://arxiv.org/abs/2405.01234", title="Mars", snippet="doi:10.1/abc", published_at=now)
    s = score("mars", r, cfg, now)
    comps = score_components("mars", r, cfg, now)
    assert abs(s - comps["weighted_sum"]) < 1e-9


def test_rerank_with_scores_includes_duplicate_penalty_and_score():
    cfg = ScoringConfig(duplicate_title_jaccard=0.9)
    now = datetime(2025, 1, 1)
    r1 = Result(url="https://site/a", title="Deep Learning Basics", snippet="", published_at=None)
    r2 = Result(url="https://site/b", title="Deep   Learning  Basics!!!", snippet="", published_at=None)
    ranked = rerank_with_scores("deep learning", [r1, r2], cfg, now)
    # First item should have zero penalty; second should have negative penalty
    assert ranked[0].components["duplicate_penalty"] == 0.0
    assert ranked[1].components["duplicate_penalty"] < 0.0
    # Final score equals weighted_sum + duplicate_penalty
    for sr in ranked:
        assert abs(sr.score - (sr.components["weighted_sum"] + sr.components["duplicate_penalty"])) < 1e-9
