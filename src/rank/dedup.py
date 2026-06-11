"""Cross-source dedup. Same story shows up on HN, Google News, and a blog
all the time — collapse them, keep the strongest representative."""
from __future__ import annotations

import re
from typing import List
from urllib.parse import urlparse

from rapidfuzz import fuzz

from ..ingest.schema import Item


_PUNCT = re.compile(r"[^\w\s]")


def _norm_title(s: str) -> str:
    return _PUNCT.sub(" ", s.lower()).strip()


def _domain_slug(url: str) -> str:
    try:
        p = urlparse(url)
    except Exception:
        return ""
    host = (p.netloc or "").lower().lstrip("www.")
    path = (p.path or "").rstrip("/").lower()
    return f"{host}{path}"


def dedup(items: List[Item], title_threshold: float = 0.7) -> List[Item]:
    """Greedy clustering — first item wins its slot; later near-duplicates merge into it.

    `title_threshold` is a ratio 0..1 against rapidfuzz token_set_ratio/100.
    Ties / near-matches keep the higher-`score` representative.
    """
    threshold_pct = title_threshold * 100.0
    kept: list[Item] = []
    norms: list[str] = []
    domains: list[str] = []

    for it in items:
        n = _norm_title(it.title)
        d = _domain_slug(it.url)
        matched_idx = -1
        for i, (kn, kd) in enumerate(zip(norms, domains)):
            same_domain = bool(d) and d == kd
            ratio = fuzz.token_set_ratio(n, kn) if (n and kn) else 0
            if same_domain or ratio >= threshold_pct:
                matched_idx = i
                break

        if matched_idx == -1:
            kept.append(it)
            norms.append(n)
            domains.append(d)
            continue

        existing = kept[matched_idx]
        also = existing.extra.setdefault("also_seen_in", [])
        also.append({"source": it.source, "url": it.url, "title": it.title})
        # Keep whichever representative has the stronger raw score.
        if it.score > existing.score:
            for k in ("also_seen_in",):
                it.extra.setdefault(k, []).extend(existing.extra.get(k, []))
            it.extra["also_seen_in"].append(
                {"source": existing.source, "url": existing.url, "title": existing.title}
            )
            kept[matched_idx] = it
            norms[matched_idx] = _norm_title(it.title)
            domains[matched_idx] = _domain_slug(it.url)

    return kept
