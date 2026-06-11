"""Queue + posted_log roundtrip. Each test runs from its own tmp cwd so the
real data/ directory is never touched."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.post import queue as q


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path: Path, monkeypatch):
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def test_load_queue_when_missing():
    assert q.load_queue() == {"generated_at": None, "tweets": []}
    assert q.load_posted_log() == {"hashes": [], "entries": []}


def test_write_then_next_unposted():
    drafts = [{"text": f"tweet {i}", "based_on": "x", "format": "y"} for i in range(4)]
    queue = q.write_queue_from_drafts(drafts)
    assert len(queue["tweets"]) == 4
    assert queue["generated_at"] is not None
    assert q.next_unposted()["text"] == "tweet 0"


def test_mark_posted_advances_queue_and_logs():
    drafts = [{"text": f"tweet {i}", "based_on": "x", "format": "y"} for i in range(4)]
    queue = q.write_queue_from_drafts(drafts)
    first_id = queue["tweets"][0]["id"]
    q.mark_posted(first_id, tweet_id="X_TWEET_ID_123")

    after = q.load_queue()
    assert after["tweets"][0]["posted"] is True
    assert after["tweets"][0]["tweet_id"] == "X_TWEET_ID_123"
    assert after["tweets"][0]["posted_at"] is not None
    assert q.next_unposted()["text"] == "tweet 1"

    log = q.load_posted_log()
    assert q._hash_text("tweet 0") in log["hashes"]
    assert any(e["tweet_id"] == "X_TWEET_ID_123" for e in log["entries"])


def test_posted_hashes_returns_set():
    drafts = [{"text": f"tweet {i}", "based_on": "x", "format": "y"} for i in range(4)]
    queue = q.write_queue_from_drafts(drafts)
    q.mark_posted(queue["tweets"][0]["id"], tweet_id="A")
    hs = q.posted_hashes()
    assert isinstance(hs, set)
    assert q._hash_text("tweet 0") in hs


def test_mark_posted_dedupes_hash_but_logs_every_entry():
    drafts = [{"text": "same", "based_on": "x", "format": "y"} for _ in range(4)]
    queue = q.write_queue_from_drafts(drafts)
    q.mark_posted(queue["tweets"][0]["id"], tweet_id="A")
    q.mark_posted(queue["tweets"][1]["id"], tweet_id="B")
    log = q.load_posted_log()
    # The hash list is a set-like dedup; the entries list is an append-only log.
    assert log["hashes"].count(q._hash_text("same")) == 1
    assert len(log["entries"]) == 2
