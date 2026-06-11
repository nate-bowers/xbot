"""Validator is the load-bearing safety net: it stops bad model output from
ever reaching the queue. These tests exercise every rejection path."""
from __future__ import annotations

import json

import pytest

from src.generate.draft import (
    DraftValidationError,
    MAX_TWEET_LEN,
    TWEET_COUNT,
    _hash_text,
    parse_and_validate,
)


def _payload(texts: list[str]) -> str:
    return json.dumps({"tweets": [{"text": t, "based_on": "x", "format": "y"} for t in texts]})


def test_happy_path():
    out = parse_and_validate(_payload(["a", "b", "c", "d"]))
    assert [t.text for t in out] == ["a", "b", "c", "d"]


def test_strips_markdown_fences():
    raw = "```json\n" + _payload(["a", "b", "c", "d"]) + "\n```"
    out = parse_and_validate(raw)
    assert len(out) == TWEET_COUNT


def test_recovers_from_preamble():
    raw = "here you go!\n" + _payload(["a", "b", "c", "d"]) + "\nlet me know"
    out = parse_and_validate(raw)
    assert len(out) == TWEET_COUNT


def test_rejects_wrong_count():
    with pytest.raises(DraftValidationError, match="expected 4"):
        parse_and_validate(_payload(["a", "b", "c"]))


def test_rejects_too_long():
    too_long = "x" * (MAX_TWEET_LEN + 1)
    with pytest.raises(DraftValidationError, match=f"max {MAX_TWEET_LEN}"):
        parse_and_validate(_payload([too_long, "b", "c", "d"]))


@pytest.mark.parametrize(
    "bad_text",
    [
        "check it: https://example.com",
        "go to www.example.com now",
        "see HTTP://thing.io for context",  # case-insensitive
    ],
)
def test_rejects_urls(bad_text):
    with pytest.raises(DraftValidationError, match="contains a URL"):
        parse_and_validate(_payload([bad_text, "b", "c", "d"]))


def test_rejects_empty_text():
    with pytest.raises(DraftValidationError, match="empty text"):
        parse_and_validate(_payload(["", "b", "c", "d"]))


def test_rejects_intra_batch_duplicates():
    with pytest.raises(DraftValidationError, match="duplicates another tweet"):
        parse_and_validate(_payload(["same", "same", "c", "d"]))


def test_rejects_previously_posted_duplicate():
    posted = {_hash_text("Already Tweeted This")}
    with pytest.raises(DraftValidationError, match="previously posted"):
        parse_and_validate(_payload(["already tweeted this", "b", "c", "d"]), posted_hashes=posted)


def test_rejects_non_json():
    with pytest.raises(DraftValidationError, match="not JSON"):
        parse_and_validate("definitely not json")


def test_rejects_missing_tweets_key():
    with pytest.raises(DraftValidationError, match="missing top-level"):
        parse_and_validate(json.dumps({"items": []}))


def test_rejects_non_list_tweets():
    with pytest.raises(DraftValidationError, match="must be a list"):
        parse_and_validate(json.dumps({"tweets": "nope"}))
