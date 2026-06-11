"""Evergreen pool: pop is destructive, empty returns None, save survives roundtrip."""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from src.post import evergreen


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path: Path, monkeypatch):
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def _seed(*tweets: str) -> None:
    Path("data/evergreen.json").write_text(json.dumps({"tweets": list(tweets)}))


def test_pop_when_missing_returns_none():
    assert evergreen.pop_random() is None
    assert evergreen.remaining() == 0


def test_pop_when_empty_returns_none():
    _seed()
    assert evergreen.pop_random() is None


def test_pop_returns_a_tweet_and_decrements_pool():
    _seed("a", "b", "c")
    rng = random.Random(42)
    got = evergreen.pop_random(rng)
    assert got in {"a", "b", "c"}
    assert evergreen.remaining() == 2


def test_pop_is_destructive_across_calls():
    _seed("a", "b", "c")
    rng = random.Random(0)
    seen = set()
    for _ in range(3):
        t = evergreen.pop_random(rng)
        assert t is not None
        seen.add(t)
    assert seen == {"a", "b", "c"}
    assert evergreen.remaining() == 0
    assert evergreen.pop_random(rng) is None


def test_pop_persists_to_disk():
    _seed("x", "y")
    rng = random.Random(1)
    evergreen.pop_random(rng)
    on_disk = json.loads(Path("data/evergreen.json").read_text())
    assert len(on_disk["tweets"]) == 1
