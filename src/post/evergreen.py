"""Evergreen tweet pool — fallback when the daily queue is empty.

The pool is a JSON list of plain tweet strings. Pop is destructive: once a
tweet is drawn it's removed from the file forever, so the cron won't pick
the same line twice. When the file is empty (or missing), `pop_random`
returns None and the cron logs a no-op.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional


EVERGREEN_PATH = Path("data/evergreen.json")


def _load() -> dict:
    if not EVERGREEN_PATH.exists():
        return {"tweets": []}
    with EVERGREEN_PATH.open() as f:
        return json.load(f)


def _save(data: dict) -> None:
    EVERGREEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVERGREEN_PATH.open("w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def remaining() -> int:
    return len(_load().get("tweets", []))


def peek_random(rng: Optional[random.Random] = None) -> Optional[str]:
    """Return a uniformly-random tweet without modifying the pool. None if empty."""
    pool = _load().get("tweets", [])
    if not pool:
        return None
    r = rng or random
    return pool[r.randrange(len(pool))]


def remove(text: str) -> bool:
    """Remove the first occurrence of `text` from the pool. Returns True if found."""
    data = _load()
    pool = data.get("tweets", [])
    try:
        pool.remove(text)
    except ValueError:
        return False
    data["tweets"] = pool
    _save(data)
    return True


def pop_random(rng: Optional[random.Random] = None) -> Optional[str]:
    """Peek and remove in one shot. Used where the caller wants destructive
    semantics directly (e.g. tests). Production callers should use peek_random
    + remove so a failed post doesn't burn an evergreen entry."""
    chosen = peek_random(rng)
    if chosen is not None:
        remove(chosen)
    return chosen
