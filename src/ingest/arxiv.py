"""arXiv ingest via the Atom export API (no key required)."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, List

import feedparser
import requests

from .schema import Item

_BASE = "http://export.arxiv.org/api/query"
_TIMEOUT = 20


def _build_query(categories: Iterable[str]) -> str:
    return "+OR+".join(f"cat:{c}" for c in categories)


def _parse_ts(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None) or entry.get(key) if hasattr(entry, "get") else None
        if val:
            return datetime(*val[:6])
    return datetime.utcnow()


def fetch(
    categories: Iterable[str] = ("cs.AI", "cs.LG", "cs.CL"),
    max_results: int = 40,
) -> List[Item]:
    query = _build_query(categories)
    url = (
        f"{_BASE}?search_query={query}"
        f"&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"
    )
    r = requests.get(url, timeout=_TIMEOUT)
    r.raise_for_status()
    parsed = feedparser.parse(r.content)
    items: list[Item] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").replace("\n", " ").strip()
        if not title:
            continue
        link = entry.get("link") or ""
        ts = _parse_ts(entry)
        summary = (entry.get("summary") or "").replace("\n", " ").strip()
        if len(summary) > 500:
            summary = summary[:497] + "..."
        items.append(
            Item(
                title=title,
                url=link,
                source="arxiv",
                timestamp=ts,
                score=0.0,
                summary=summary,
                extra={
                    "arxiv_id": entry.get("id"),
                    "authors": [a.get("name") for a in entry.get("authors", []) if a.get("name")],
                },
            )
        )
    return items
