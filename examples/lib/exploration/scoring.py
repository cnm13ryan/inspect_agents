"""
Scoring for candidate search results (authority/recency/topical/citation).

Deterministic, offline-friendly heuristics to rank results without external
embeddings. Designed to be plugged into planners or runners later.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field

# -------------------------
# Data Models
# -------------------------


class Result(BaseModel):
    url: str
    title: str
    snippet: str
    published_at: datetime | None = None


class ScoringConfig(BaseModel):
    w_authority: float = 0.35
    w_recency: float = 0.25
    w_topic: float = 0.30
    w_citation: float = 0.10
    domain_whitelist: list[str] = Field(default_factory=lambda: ["arxiv.org", "*.gov", "*.edu"])
    domain_blacklist: list[str] = Field(default_factory=list)
    duplicate_title_jaccard: float = 0.90


# -------------------------
# Helpers
# -------------------------


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> set[str]:
    return set(_TOKEN_RE.findall(s.lower()))


def normalize_domain(url: str) -> str:
    """Return a normalized domain for a URL.

    - Adds a default scheme if missing so urlparse can extract host
    - Lowercases and strips common prefixes and ports
    """

    raw = url.strip()
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
        raw = "http://" + raw  # scheme-less inputs
    parsed = urlparse(raw)
    host = parsed.netloc or parsed.path
    host = host.split("@")[-1]  # strip creds if present
    host = host.split(":")[0]  # strip port
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _matches_pattern(domain: str, pattern: str) -> bool:
    """Return True if domain matches a whitelist/blacklist pattern.

    Supports exact match (e.g., "arxiv.org") and suffix wildcard forms like
    "*.gov" or "*.edu" (matching both the bare TLD parent and any subdomain).
    """

    domain = domain.lower()
    pattern = pattern.lower()
    if pattern.startswith("*."):
        suffix = pattern[2:]
        return domain == suffix or domain.endswith("." + suffix)
    return domain == pattern


def domain_authority(domain: str, cfg: ScoringConfig) -> float:
    """Return a small prior for domain authority.

    - +0.5 for whitelist match
    - -0.5 for blacklist match
    - +0.2 if TLD is .gov or .edu (heuristic)
    Values are additive and then clamped to [-1, 1].
    """

    score = 0.0
    for p in cfg.domain_whitelist:
        if _matches_pattern(domain, p):
            score += 0.5
            break
    for p in cfg.domain_blacklist:
        if _matches_pattern(domain, p):
            score -= 0.5
            break

    # TLD heuristic
    if domain.endswith(".gov") or domain.endswith(".edu"):
        score += 0.2

    return max(-1.0, min(1.0, score))


def recency_weight(published_at: datetime | None, now: datetime, *, half_life_days: float = 365.0) -> float:
    """Exponential decay from 1.0 at now to ~0.5 at half-life.

    - If ``published_at`` is None, return neutral 0.0 (unknown recency).
    - Future timestamps are treated as "now" (weight 1.0).
    """

    if published_at is None:
        return 0.0

    # Normalize TZ-awareness to avoid exceptions on subtraction
    def _naive(dt: datetime) -> datetime:
        return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt

    p = _naive(published_at)
    n = _naive(now)
    dt_days = max(0.0, (n - p).total_seconds() / 86400.0)
    # Exponential decay: w = 2^(-t / half_life)
    w = 2.0 ** (-(dt_days / half_life_days))
    return float(max(0.0, min(1.0, w)))


def topical_similarity(a: str, b: str) -> float:
    """Jaccard similarity of token sets in [0,1]."""

    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    if union == 0:
        return 0.0
    return float(inter / union)


_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
_ARXIV_ID_RE = re.compile(r"\b(\d{4}\.\d{4,5})(?:v\d+)?\b")
_BRACKETED_CITE_RE = re.compile(r"\[[1-9]\d*\]")


def citation_present(*, title: str, snippet: str) -> float:
    """Heuristic citation signal: DOI, arXiv ID, or bracketed citation tokens.

    Returns a value in [0,1].
    """

    blob = f"{title} {snippet}"
    if _DOI_RE.search(blob):
        return 1.0
    if _ARXIV_ID_RE.search(blob) or "arxiv.org" in blob.lower():
        return 0.8
    if _BRACKETED_CITE_RE.search(blob):
        return 0.5
    return 0.0


def dedupe_penalty(title_a: str, title_b: str, *, threshold: float = 0.90, penalty: float = -0.15) -> float:
    """Return a small negative penalty if titles are near-duplicates.

    Uses Jaccard similarity of title tokens; if >= ``threshold`` then
    ``penalty`` is applied (negative). Otherwise 0.0.
    """

    sim = topical_similarity(title_a, title_b)
    return penalty if sim >= threshold else 0.0


def score(query: str, result: Result, cfg: ScoringConfig, now: datetime) -> float:
    """Weighted score combining authority, recency, topicality, and citations."""

    domain = normalize_domain(result.url)
    authority = domain_authority(domain, cfg)
    recency = recency_weight(result.published_at, now)
    topic = topical_similarity(query, f"{result.title} {result.snippet}")
    cite = citation_present(title=result.title, snippet=result.snippet)

    s = cfg.w_authority * authority + cfg.w_recency * recency + cfg.w_topic * topic + cfg.w_citation * cite
    return float(s)


def rerank(query: str, results: list[Result], cfg: ScoringConfig, now: datetime) -> list[Result]:
    """Stable rerank by score (desc) with a duplicate-title penalty pass.

    The duplicate penalty is applied to later duplicates only; a single
    penalty is applied if a title is considered a near-duplicate of any prior
    title in the current list.
    """

    scored: list[tuple[int, Result, float]] = []
    seen_titles: list[str] = []
    for idx, r in enumerate(results):
        base = score(query, r, cfg, now)
        pen = 0.0
        for prior in seen_titles:
            pen = dedupe_penalty(prior, r.title, threshold=cfg.duplicate_title_jaccard)
            if pen < 0.0:
                break  # apply at most once
        final = base + pen
        scored.append((idx, r, final))
        seen_titles.append(r.title)

    # Stable sort: Python's sort is stable; include original index to lock ties
    scored.sort(key=lambda t: (-t[2], t[0]))
    return [r for _, r, _ in scored]


class ScoredResult(BaseModel):
    result: Result
    score: float
    components: dict[str, float]


def score_components(query: str, result: Result, cfg: ScoringConfig, now: datetime) -> dict[str, float]:
    """Return component contributions and base weighted sum (no duplicate penalty).

    Keys:
      - authority, recency, topic, citation: component values in [0,1] (authority in [-1,1]).
      - weighted_sum: cfg-weighted sum of components (no duplicate penalty).
    """

    domain = normalize_domain(result.url)
    authority = domain_authority(domain, cfg)
    recency = recency_weight(result.published_at, now)
    topic = topical_similarity(query, f"{result.title} {result.snippet}")
    cite = citation_present(title=result.title, snippet=result.snippet)
    weighted = cfg.w_authority * authority + cfg.w_recency * recency + cfg.w_topic * topic + cfg.w_citation * cite
    return {
        "authority": float(authority),
        "recency": float(recency),
        "topic": float(topic),
        "citation": float(cite),
        "weighted_sum": float(weighted),
    }


def rerank_with_scores(query: str, results: list[Result], cfg: ScoringConfig, now: datetime) -> list[ScoredResult]:
    """Rerank and include component breakdowns and duplicate-title penalty.

    Each ScoredResult.components includes keys from score_components plus:
      - duplicate_penalty: negative penalty applied due to near-duplicate title
      - score: final score (weighted_sum + duplicate_penalty)
    """

    scored: list[tuple[int, ScoredResult]] = []
    seen_titles: list[str] = []
    for idx, r in enumerate(results):
        comps = score_components(query, r, cfg, now)
        pen = 0.0
        for prior in seen_titles:
            pen = dedupe_penalty(prior, r.title, threshold=cfg.duplicate_title_jaccard)
            if pen < 0.0:
                break
        final = comps["weighted_sum"] + pen
        comps_full = {**comps, "duplicate_penalty": float(pen), "score": float(final)}
        scored.append((idx, ScoredResult(result=r, score=float(final), components=comps_full)))
        seen_titles.append(r.title)

    scored.sort(key=lambda t: (-t[1].score, t[0]))
    return [sr for _, sr in scored]


__all__ = [
    "Result",
    "ScoringConfig",
    "normalize_domain",
    "domain_authority",
    "recency_weight",
    "topical_similarity",
    "citation_present",
    "dedupe_penalty",
    "score",
    "rerank",
    "ScoredResult",
    "score_components",
    "rerank_with_scores",
]
