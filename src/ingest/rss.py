"""Generic RSS ingest. Feed list comes from config.yaml."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Mapping

import sys

import feedparser
import requests

from .schema import Item

_TIMEOUT = 20
# Some blogs (notably TechCrunch) 403 a default urllib UA — give them a
# browserish UA when we fetch ourselves.
_UA = "Mozilla/5.0 (compatible; tweetbot/0.1; +https://github.com/)"


def _parse_ts(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key) if hasattr(entry, "get") else getattr(entry, key, None)
        if val:
            return datetime(*val[:6])
    return datetime.utcnow()


def fetch_one(name: str, url: str) -> List[Item]:
    r = requests.get(url, timeout=_TIMEOUT, headers={"User-Agent": _UA})
    r.raise_for_status()
    parsed = feedparser.parse(r.content)
    if parsed.bozo and not parsed.entries:
        # Malformed and empty - treat as a hard miss so the collector can log it.
        raise RuntimeError(f"RSS feed {name!r} returned no entries: {parsed.bozo_exception}")
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
                source=f"rss:{name}",
                timestamp=ts,
                score=0.0,
                summary=summary,
                extra={"feed": name},
            )
        )
    return items


def fetch(feeds: Iterable[Mapping[str, str]]) -> List[Item]:
    out: list[Item] = []
    for feed in feeds:
        name = feed.get("name") or feed.get("url")
        url = feed.get("url")
        if not url:
            continue
        try:
            out.extend(fetch_one(name, url))
        except Exception as e:
            # One dead feed must not kill the whole RSS pull.
            print(f"[rss] feed failed {name!r}: {e}", file=sys.stderr)
    return out
