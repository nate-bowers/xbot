"""End-to-end-ish tests for the post_next dispatch logic. Mocks the X client
and Telegram so nothing actually posts."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.post import post_next as pn
from src.post import queue as q


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path: Path, monkeypatch):
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)
    # Force dry-run off so we exercise the real post path with a mock.
    monkeypatch.setenv("DRY_RUN", "false")
    yield tmp_path


def _seed_queue(*texts: str) -> None:
    drafts = [{"text": t, "based_on": "x", "format": "y"} for t in texts]
    q.write_queue_from_drafts(drafts)


def _seed_evergreen(*texts: str) -> None:
    Path("data/evergreen.json").write_text(json.dumps({"tweets": list(texts)}))


def test_empty_queue_empty_evergreen_is_a_clean_noop(monkeypatch):
    posted = []
    monkeypatch.setattr(pn, "post_tweet", lambda t: posted.append(t) or "999")
    rc = pn.main()
    assert rc == 0
    assert posted == []


def test_uses_queue_when_queue_has_entries(monkeypatch):
    _seed_queue("a", "b", "c", "d")
    _seed_evergreen("EVERGREEN-1", "EVERGREEN-2")
    posted = []
    monkeypatch.setattr(pn, "post_tweet", lambda t: posted.append(t) or "1")
    monkeypatch.setattr(pn.telegram, "send", lambda msg: True)
    rc = pn.main()
    assert rc == 0
    assert posted == ["a"]
    # Evergreen untouched.
    eg = json.loads(Path("data/evergreen.json").read_text())
    assert eg["tweets"] == ["EVERGREEN-1", "EVERGREEN-2"]


def test_falls_back_to_evergreen_when_queue_empty(monkeypatch):
    _seed_evergreen("only-evergreen")
    posted = []
    monkeypatch.setattr(pn, "post_tweet", lambda t: posted.append(t) or "42")
    monkeypatch.setattr(pn.telegram, "send", lambda msg: True)
    rc = pn.main()
    assert rc == 0
    assert posted == ["only-evergreen"]
    # Evergreen popped.
    eg = json.loads(Path("data/evergreen.json").read_text())
    assert eg["tweets"] == []
    # Posted log records it as evergreen-sourced.
    log = q.load_posted_log()
    assert log["entries"][-1]["tweet_id"] == "42"
    assert log["entries"][-1]["source"] == "evergreen"


def test_falls_back_when_all_queue_entries_already_posted(monkeypatch):
    _seed_queue("a")
    # Mark the one entry as posted.
    queue = q.load_queue()
    q.mark_posted(queue["tweets"][0]["id"], tweet_id="prev")
    _seed_evergreen("backup")
    posted = []
    monkeypatch.setattr(pn, "post_tweet", lambda t: posted.append(t) or "99")
    monkeypatch.setattr(pn.telegram, "send", lambda msg: True)
    rc = pn.main()
    assert rc == 0
    assert posted == ["backup"]


def test_dry_run_does_not_consume_evergreen(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    _seed_evergreen("preview-me")
    posted = []
    monkeypatch.setattr(pn, "post_tweet", lambda t: posted.append(t) or "X")
    rc = pn.main()
    assert rc == 0
    assert posted == []  # never called
    # Evergreen pool unchanged.
    eg = json.loads(Path("data/evergreen.json").read_text())
    assert eg["tweets"] == ["preview-me"]


def test_failed_post_does_not_consume_evergreen(monkeypatch):
    from src.post.xclient import XPostError
    _seed_evergreen("don't burn me")
    def fail(_): raise XPostError("simulated", status=500, code=None)
    monkeypatch.setattr(pn, "post_tweet", fail)
    monkeypatch.setattr(pn.telegram, "send", lambda msg: True)
    rc = pn.main()
    assert rc == 1
    # Pool intact — the entry isn't burned because the post failed.
    eg = json.loads(Path("data/evergreen.json").read_text())
    assert eg["tweets"] == ["don't burn me"]


def test_evergreen_already_posted_is_skipped_not_reposted(monkeypatch):
    # Pre-seed the posted log with the evergreen text's hash so the
    # belt-and-suspenders dedup catches it.
    q.record_posted("dup", tweet_id="earlier", source="evergreen")
    _seed_evergreen("dup")
    posted = []
    monkeypatch.setattr(pn, "post_tweet", lambda t: posted.append(t) or "X")
    rc = pn.main()
    assert rc == 0
    assert posted == []  # never reached the API
