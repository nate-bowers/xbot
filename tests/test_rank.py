"""Rank/dedup correctness tests. Pure functions, no network."""
from __future__ import annotations

from datetime import datetime, timedelta

from src.ingest.schema import Item
from src.rank.dedup import dedup
from src.rank.rank import rank
from src.rank.score import freshness, score_items


def _it(title: str, source: str, hours_old: float, score: float = 0.0, url: str = "") -> Item:
    return Item(
        title=title,
        url=url or f"https://example.com/{title.replace(' ', '-')}",
        source=source,
        timestamp=datetime.utcnow() - timedelta(hours=hours_old),
        score=score,
    )


def test_dedup_collapses_near_duplicate_titles():
    a = _it("OpenAI announces GPT-7 with multimodal reasoning", "hackernews", 1, score=500)
    b = _it("OpenAI Announces GPT-7 With Multimodal Reasoning!", "googlenews", 1)
    c = _it("totally unrelated story about JPL rover", "hackernews", 1, score=200)
    out = dedup([a, b, c], title_threshold=0.7)
    assert len(out) == 2
    kept = next(o for o in out if "GPT-7" in o.title)
    assert kept.extra.get("also_seen_in"), "merged source should be recorded"


def test_dedup_keeps_higher_score_representative():
    weak = _it("Same story", "googlenews", 1, score=0)
    strong = _it("Same story!", "hackernews", 1, score=1000)
    out = dedup([weak, strong], title_threshold=0.7)
    assert len(out) == 1
    # Strong wins because it has a meaningfully higher raw score.
    assert out[0].source == "hackernews"


def test_freshness_decay():
    now = datetime.utcnow()
    fresh = _it("x", "hackernews", 0.0)
    aged = _it("y", "hackernews", 12.0)
    very_old = _it("z", "hackernews", 48.0)
    assert freshness(fresh, half_life_hours=12, now=now) > 0.99
    # 12h half-life means age=12h is ~0.5.
    assert 0.49 < freshness(aged, half_life_hours=12, now=now) < 0.51
    assert freshness(very_old, half_life_hours=12, now=now) < 0.1


def test_score_items_attaches_breakdown():
    items = [
        _it("a", "hackernews", 1, score=100),
        _it("b", "hackernews", 1, score=500),
    ]
    cfg = {
        "freshness_half_life_hours": 12,
        "weights": {"freshness": 0.5, "signal": 0.5},
        "source_weights": {"hackernews": 1.0},
    }
    scored = score_items(items, cfg)
    for it, val in scored:
        assert "score_breakdown" in it.extra
        assert val > 0
    # Higher raw score should produce a higher final score, all else equal.
    high = next(v for it, v in scored if it.title == "b")
    low = next(v for it, v in scored if it.title == "a")
    assert high > low


def test_rank_returns_top_n_sorted():
    items = [
        _it("brand new", "hackernews", 0.1, score=10),
        _it("medium fresh", "hackernews", 6, score=10),
        _it("ancient", "hackernews", 100, score=10),
    ]
    cfg = {
        "top_n": 2,
        "freshness_half_life_hours": 12,
        "weights": {"freshness": 1.0, "signal": 0.0},
        "source_weights": {"hackernews": 1.0},
    }
    top = rank(items, cfg)
    assert len(top) == 2
    # Freshest first.
    assert top[0].title == "brand new"
