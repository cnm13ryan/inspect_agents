from __future__ import annotations

import random
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

try:
    # Prefer pydantic BaseModel when available in this repo (it is used broadly)
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover - fallback to light shim if pydantic missing

    @dataclass
    class _ShimModel:  # type: ignore
        pass

    BaseModel = _ShimModel  # type: ignore

    def Field(default=None, **_):  # noqa: N802
        return default  # type: ignore


class ExplorationConfig(BaseModel):
    """Deterministic exploration planner configuration.

    Notes
    - Keep pure-Python and offline; no network or heavy NLP deps.
    - Determinism: any shuffling/sampling uses Random(seed).
    """

    breadth: int = Field(3, ge=1)
    depth: int = Field(2, ge=0)
    seed: int = 0
    convergence_delta: float = Field(0.05, ge=0.0, le=1.0)
    max_queries: int = Field(12, ge=1)
    synonym_expansion: bool = True
    site_hints: list[str] | None = None


class QuerySpec(BaseModel):
    """Single query plan item."""

    query: str
    depth: int
    tags: list[str] = Field(default_factory=list)
    target_domains: list[str] = Field(default_factory=list)


_STOPWORDS: set[str] = {
    "the",
    "a",
    "an",
    "of",
    "and",
    "or",
    "on",
    "to",
    "in",
    "for",
    "with",
    "about",
    "how",
    "what",
    "why",
    "is",
    "are",
    "vs",
    "vs.",
}


_SYNONYMS: dict[str, list[str]] = {
    "research": ["study", "analysis", "review"],
    "trend": ["trajectory", "pattern", "development"],
    "ai": ["artificial intelligence"],
    "llm": ["large language model", "foundation model"],
    "ranking": ["scoring", "ordering"],
    "compare": ["benchmark", "evaluate"],
    "security": ["cybersecurity", "information security"],
    "privacy": ["data protection"],
    "framework": ["library", "toolkit"],
    "method": ["approach", "technique"],
    "impact": ["effect", "outcome"],
    "performance": ["latency", "throughput", "benchmark"],
    "paper": ["preprint", "article"],
}


_TEMPORAL_TOKENS = {
    "today",
    "this year",
    "latest",
    "recent",
    "now",
    "current",
    "breaking",
    "update",
}


def _normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _normalize_query_key(s: str) -> str:
    # lowercased, whitespace-collapsed; keep operators intact
    return _normalize_whitespace(s).lower()


def _norm_domain(d: str) -> str:
    d = d.lower().strip()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.split("/")[0]


def _year_tokens_present(text: str) -> bool:
    return re.search(r"\b(19\d{2}|20\d{2})\b", text) is not None


def classify_prompt(prompt: str) -> str:
    """Classify a prompt as "fresh" or "evergreen" using lightweight heuristics.

    - If it contains temporal tokens or explicit years, mark as "fresh".
    - Otherwise, treat as "evergreen".
    Deterministic and offline.
    """

    p = prompt.lower()
    if _year_tokens_present(p):
        return "fresh"
    for tok in _TEMPORAL_TOKENS:
        if tok in p:
            return "fresh"
    return "evergreen"


def _extract_keywords(prompt: str, max_k: int = 6) -> list[str]:
    # Simple keyword extraction: alphanum words > 3 chars, exclude stopwords
    words = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\-]+", prompt.lower())
    cand = [w.strip("-_") for w in words if len(w) > 3 and w not in _STOPWORDS]
    # Deduplicate preserving order by first occurrence; prefer longer tokens first
    seen: set[str] = set()
    ordered = []
    for w in sorted(cand, key=lambda x: (-len(x), cand.index(x))):
        if w not in seen:
            seen.add(w)
            ordered.append(w)
        if len(ordered) >= max_k:
            break
    return ordered


def _synonym_variants(prompt: str, prng: random.Random) -> list[str]:
    base = prompt
    kws = _extract_keywords(prompt)
    variants: list[str] = []
    for kw in kws:
        syns = _SYNONYMS.get(kw)
        if not syns:
            continue
        # Replace first whole-word occurrence (case-insensitive)
        for syn in syns:
            pattern = re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE)
            repl = syn
            if pattern.search(base):
                v = pattern.sub(repl, base, count=1)
            else:
                # fallback: append synonym near keyword for coverage
                v = f"{base} {repl}"
            variants.append(_normalize_whitespace(v))
    # Ensure deterministic order; shuffle with seed for variety but reproducible
    prng.shuffle(variants)
    # Deduplicate while preserving shuffled order
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        k = _normalize_query_key(v)
        if k not in seen:
            seen.add(k)
            out.append(v)
    return out


def _operator_variants(prompt: str) -> list[str]:
    kws = _extract_keywords(prompt, max_k=4)
    variants: list[str] = []
    if kws:
        # intitle with the most salient keyword
        k0 = kws[0]
        variants.append(f'intitle:"{k0}" {prompt}')
    if len(kws) >= 2:
        k1 = kws[1]
        variants.append(f'intitle:"{k1}" {prompt}')
    return [_normalize_whitespace(v) for v in variants]


def _recency_variants(prompt: str) -> list[str]:
    # Use timezone-aware UTC now to avoid deprecation warnings
    this_year = datetime.now(UTC).year
    last_year = this_year - 1
    rng = f"{last_year}..{this_year}"
    return [
        _normalize_whitespace(f"{prompt} {rng}"),
        _normalize_whitespace(f"{prompt} latest"),
    ]


def _site_variants(prompt: str, sites: Sequence[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for site in sites:
        d = _norm_domain(site)
        out.append((f"site:{d} {prompt}", d))
    return [(_normalize_whitespace(q), d) for q, d in out]


def generate_seed_queries(prompt: str, cfg: ExplorationConfig) -> list[QuerySpec]:
    """Generate initial seed queries from a prompt.

    Strategy (deterministic):
    - Always include the base prompt as a seed.
    - Add up to breadth-1 diverse variants from: site hints, operator variants, synonyms, and recency (if fresh).
    - Dedupe by normalized query.
    """

    prng = random.Random(cfg.seed)
    base = _normalize_whitespace(prompt)
    cls = classify_prompt(base)

    candidates: list[QuerySpec] = [QuerySpec(query=base, depth=0, tags=["seed", cls], target_domains=[])]

    # Site hints first for diversity
    if cfg.site_hints:
        for q, d in _site_variants(base, cfg.site_hints):
            candidates.append(QuerySpec(query=q, depth=0, tags=["seed", cls, f"site:{d}"], target_domains=[d]))

    # Operator variants
    for v in _operator_variants(base):
        candidates.append(QuerySpec(query=v, depth=0, tags=["seed", cls, "op:intitle"], target_domains=[]))

    # Synonym variants
    if cfg.synonym_expansion:
        for v in _synonym_variants(base, prng):
            candidates.append(QuerySpec(query=v, depth=0, tags=["seed", cls, "synonym"], target_domains=[]))

    # Recency if fresh
    if cls == "fresh":
        for v in _recency_variants(base):
            candidates.append(QuerySpec(query=v, depth=0, tags=["seed", cls, "recency"], target_domains=[]))

    # Dedupe and bound by breadth
    seen: set[str] = set()
    deduped: list[QuerySpec] = []
    for q in candidates:
        k = _normalize_query_key(q.query)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(q)

    # Keep base first; then pick up to breadth-1 others deterministically
    if len(deduped) <= cfg.breadth:
        return deduped[: cfg.max_queries]

    # Keep base (index 0), sample the rest with seed
    rest = deduped[1:]
    prng.shuffle(rest)
    selected = [deduped[0]] + rest[: max(0, min(cfg.breadth - 1, len(rest)))]
    return selected[: cfg.max_queries]


def _neighbor_expansions(item: QuerySpec, cfg: ExplorationConfig, prng: random.Random) -> list[QuerySpec]:
    base = item.query
    cls_tag = "fresh" if "fresh" in item.tags else ("evergreen" if "evergreen" in item.tags else None)

    neighbors: list[QuerySpec] = []

    # Expand with operator variants
    for v in _operator_variants(base):
        neighbors.append(
            QuerySpec(
                query=v, depth=item.depth + 1, tags=item.tags + ["op:intitle"], target_domains=item.target_domains
            )
        )

    # Expand with site hints, prefer distinct domains
    domains_used = set(item.target_domains)
    if cfg.site_hints:
        for q, d in _site_variants(base, cfg.site_hints):
            if d in domains_used:
                continue
            neighbors.append(
                QuerySpec(
                    query=q,
                    depth=item.depth + 1,
                    tags=item.tags + [f"site:{d}"],
                    target_domains=list(set(item.target_domains + [d])),
                )
            )
            domains_used.add(d)

    # Synonyms
    if cfg.synonym_expansion:
        for v in _synonym_variants(base, prng):
            neighbors.append(
                QuerySpec(
                    query=v, depth=item.depth + 1, tags=item.tags + ["synonym"], target_domains=item.target_domains
                )
            )

    # Recency tweaks for fresh topics
    if cls_tag == "fresh":
        for v in _recency_variants(base):
            neighbors.append(
                QuerySpec(
                    query=v, depth=item.depth + 1, tags=item.tags + ["recency"], target_domains=item.target_domains
                )
            )

    # Deterministic shuffle for variety
    prng.shuffle(neighbors)
    # Bound local branching factor (breadth)
    return neighbors[: cfg.breadth]


def expand_frontier(seeds: list[QuerySpec], cfg: ExplorationConfig) -> list[QuerySpec]:
    """Breadth-first expansion with dedupe, bounded breadth/depth, and early stop.

    - Dedupe by normalized query key.
    - Prefer domain diversity when site hints are present.
    - Stop if marginal gain < convergence_delta or max_queries reached.
    """

    prng = random.Random(cfg.seed)

    all_items: list[QuerySpec] = []
    seen: set[str] = set()

    # Seed layer (depth 0)
    frontier: list[QuerySpec] = []
    for s in seeds:
        k = _normalize_query_key(s.query)
        if k in seen:
            continue
        seen.add(k)
        all_items.append(s)
        frontier.append(s)
        if len(all_items) >= cfg.max_queries:
            return all_items

    prev_total = len(all_items)

    # BFS up to cfg.depth (exclusive of seeds at depth 0)
    for depth in range(1, cfg.depth + 1):
        next_frontier: list[QuerySpec] = []
        for item in frontier:
            # Only expand items whose current depth is less than this layer
            if item.depth < depth:
                for n in _neighbor_expansions(item, cfg, prng):
                    k = _normalize_query_key(n.query)
                    if k in seen:
                        continue
                    seen.add(k)
                    all_items.append(n)
                    next_frontier.append(n)
                    if len(all_items) >= cfg.max_queries:
                        return all_items

        # Early stop on marginal gain
        added = len(all_items) - prev_total
        gain = 0.0 if prev_total == 0 else (added / prev_total)
        if added == 0 or gain < cfg.convergence_delta:
            break
        frontier = next_frontier
        prev_total = len(all_items)

    return all_items


def plan(prompt: str, cfg: ExplorationConfig) -> list[QuerySpec]:
    """Full planning pipeline: classify → seed → BFS expand → early stop.

    Returns at most `cfg.max_queries` QuerySpec items with depth ≤ cfg.depth.
    """

    seeds = generate_seed_queries(prompt, cfg)
    items = expand_frontier(seeds, cfg)
    # Ensure global cap (though functions already enforce it)
    return items[: cfg.max_queries]
