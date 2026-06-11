"""Google News ingest via the public RSS search endpoint (no key required)."""
from __future__ import annotations

import sys
from datetime import datetime
from typing import Iterable, List
from urllib.parse import quote_plus

import feedparser
import requests

from .schema import Item

_BASE = "https://news.google.com/rss/search"
_TIMEOUT = 20


def _parse_ts(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key) if hasattr(entry, "get") else getattr(entry, key, None)
        if val:
            return datetime(*val[:6])
    return datetime.utcnow()


def _fetch_query(query: str) -> List[Item]:
    url = f"{_BASE}?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    r = requests.get(url, timeout=_TIMEOUT)
    r.raise_for_status()
    parsed = feedparser.parse(r.content)
    items: list[Item] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        link = entry.get("link") or ""
        if not title or not link:
            continue
        ts = _parse_ts(entry)
        summary = (entry.get("summary") or "").strip()
        if len(summary) > 400:
            summary = summary[:397] + "..."
        items.append(
            Item(
                title=title,
                url=link,
                source="googlenews",
                timestamp=ts,
                score=0.0,
                summary=summary,
                extra={"query": query, "publisher": entry.get("source", {}).get("title")},
            )
        )
    return items


def fetch(queries: Iterable[str]) -> List[Item]:
    out: list[Item] = []
    for q in queries:
        try:
            out.extend(_fetch_query(q))
        except Exception as e:
            # Per-query failure should not kill the source.
            print(f"[googlenews] query failed {q!r}: {e}", file=sys.stderr)
    return out
