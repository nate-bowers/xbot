"""Dedup + score, then return the top-N items."""
from __future__ import annotations

from typing import List, Optional

from ..ingest.schema import Item
from .dedup import dedup
from .score import score_items


def rank(items: List[Item], rank_cfg: dict, n: Optional[int] = None) -> List[Item]:
    n = n if n is not None else int(rank_cfg.get("top_n", 20))
    title_threshold = float(rank_cfg.get("dedup_title_threshold", 0.7))
    deduped = dedup(items, title_threshold=title_threshold)
    scored = score_items(deduped, rank_cfg)
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [it for it, _ in scored[:n]]
