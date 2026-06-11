"""Combine freshness, signal, and per-source weighting into a single score."""
from __future__ import annotations

import math
from datetime import datetime
from typing import List

from ..ingest.schema import Item


_ARXIV_NOVELTY_BASELINE = 100.0


def _source_family(source: str) -> str:
    if source.startswith("rss:"):
        return "rss"
    return source


def freshness(item: Item, half_life_hours: float, now: datetime) -> float:
    age = item.age_hours(now)
    return math.exp(-math.log(2.0) * age / max(half_life_hours, 0.1))


def _normalize_signal(items: List[Item]) -> dict[int, float]:
    """Map per-item raw signal to [0, 1] using max within each source family."""
    family_max: dict[str, float] = {}
    for it in items:
        fam = _source_family(it.source)
        raw = it.score if it.score > 0 else (_ARXIV_NOVELTY_BASELINE if fam == "arxiv" else 0.0)
        if raw > family_max.get(fam, 0.0):
            family_max[fam] = raw
    out: dict[int, float] = {}
    for it in items:
        fam = _source_family(it.source)
        raw = it.score if it.score > 0 else (_ARXIV_NOVELTY_BASELINE if fam == "arxiv" else 0.0)
        cap = family_max.get(fam, 0.0)
        out[id(it)] = (raw / cap) if cap > 0 else 0.0
    return out


def score_items(items: List[Item], rank_cfg: dict, now: datetime | None = None) -> list[tuple[Item, float]]:
    now = now or datetime.utcnow()
    half_life = float(rank_cfg.get("freshness_half_life_hours", 12.0))
    weights = rank_cfg.get("weights", {}) or {}
    w_f = float(weights.get("freshness", 0.6))
    w_s = float(weights.get("signal", 0.4))
    src_weights = rank_cfg.get("source_weights", {}) or {}

    sig = _normalize_signal(items)
    scored: list[tuple[Item, float]] = []
    for it in items:
        fresh = freshness(it, half_life, now)
        signal_norm = sig[id(it)]
        family = _source_family(it.source)
        src_w = float(src_weights.get(family, 1.0))
        combined = (fresh * w_f + signal_norm * w_s) * src_w
        # Stash the components for transparency / debugging.
        it.extra["score_breakdown"] = {
            "freshness": round(fresh, 4),
            "signal_norm": round(signal_norm, 4),
            "source_weight": src_w,
            "final": round(combined, 4),
        }
        scored.append((it, combined))
    return scored
