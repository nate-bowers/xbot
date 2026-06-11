"""Run every ingest client, catch per-source exceptions, log what each returned.

Diagnostic prints go to stderr so callers can pipe stdout (e.g. when redirecting
the rendered prompt to a file)."""
from __future__ import annotations

import sys
from typing import List

from . import arxiv, googlenews, hackernews, rss
from .schema import Item


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def collect(config: dict) -> List[Item]:
    items: list[Item] = []
    ing = (config or {}).get("ingest", {}) or {}

    hn_cfg = ing.get("hackernews", {}) or {}
    if hn_cfg.get("enabled", True):
        try:
            got = hackernews.fetch(
                front_page_hits=int(hn_cfg.get("front_page_hits", 30)),
                high_score_min_points=int(hn_cfg.get("high_score_min_points", 150)),
                high_score_hits=int(hn_cfg.get("high_score_hits", 30)),
            )
            _log(f"[collect] hackernews: {len(got)} items")
            items.extend(got)
        except Exception as e:
            _log(f"[collect] hackernews failed: {e}")

    ax_cfg = ing.get("arxiv", {}) or {}
    if ax_cfg.get("enabled", True):
        try:
            got = arxiv.fetch(
                categories=ax_cfg.get("categories", ["cs.AI", "cs.LG", "cs.CL"]),
                max_results=int(ax_cfg.get("max_results", 40)),
            )
            _log(f"[collect] arxiv: {len(got)} items")
            items.extend(got)
        except Exception as e:
            _log(f"[collect] arxiv failed: {e}")

    gn_cfg = ing.get("google_news", {}) or {}
    if gn_cfg.get("enabled", True):
        try:
            got = googlenews.fetch(gn_cfg.get("queries", []))
            _log(f"[collect] googlenews: {len(got)} items")
            items.extend(got)
        except Exception as e:
            _log(f"[collect] googlenews failed: {e}")

    rss_cfg = ing.get("rss", {}) or {}
    if rss_cfg.get("enabled", True):
        try:
            got = rss.fetch(rss_cfg.get("feeds", []))
            _log(f"[collect] rss: {len(got)} items")
            items.extend(got)
        except Exception as e:
            _log(f"[collect] rss failed: {e}")

    _log(f"[collect] total: {len(items)} items")
    return items
