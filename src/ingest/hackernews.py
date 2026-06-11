"""Hacker News ingest via the Algolia public API (no key required)."""
from __future__ import annotations

from datetime import datetime
from typing import List

import requests

from .schema import Item

_BASE = "https://hn.algolia.com/api/v1"
_TIMEOUT = 15


def _hit_to_item(hit: dict) -> Item | None:
    url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
    title = hit.get("title") or hit.get("story_title") or ""
    if not title:
        return None
    created = hit.get("created_at_i")
    if created is None:
        return None
    return Item(
        title=title,
        url=url,
        source="hackernews",
        timestamp=datetime.utcfromtimestamp(int(created)),
        score=float(hit.get("points") or 0),
        summary="",
        extra={
            "hn_id": hit.get("objectID"),
            "num_comments": hit.get("num_comments"),
            "author": hit.get("author"),
        },
    )


def fetch(
    front_page_hits: int = 30,
    high_score_min_points: int = 150,
    high_score_hits: int = 30,
) -> List[Item]:
    items: list[Item] = []
    seen: set[str] = set()

    def _ingest(params: dict) -> None:
        r = requests.get(f"{_BASE}/search", params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        for hit in r.json().get("hits", []):
            item = _hit_to_item(hit)
            if not item:
                continue
            key = item.extra.get("hn_id") or item.url
            if key in seen:
                continue
            seen.add(key)
            items.append(item)

    _ingest({"tags": "front_page", "hitsPerPage": front_page_hits})

    r = requests.get(
        f"{_BASE}/search_by_date",
        params={
            "tags": "story",
            "numericFilters": f"points>{high_score_min_points}",
            "hitsPerPage": high_score_hits,
        },
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    for hit in r.json().get("hits", []):
        item = _hit_to_item(hit)
        if not item:
            continue
        key = item.extra.get("hn_id") or item.url
        if key in seen:
            continue
        seen.add(key)
        items.append(item)

    return items
