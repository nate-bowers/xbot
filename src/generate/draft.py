"""Parse and validate model output. Two modes:

- cowork (production): the daily Cowork task runs `draft-prompt`, produces JSON
  inline using the Max subscription, writes it to a file, then runs
  `draft-commit` which calls `parse_and_validate` + the queue writer.
- local-test: paste sample JSON to validate the parser end-to-end without any
  paid call. There is intentionally no Anthropic API key path here.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import List


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)
_URL_HINT = re.compile(r"\b(?:https?://|www\.)", re.IGNORECASE)
MAX_TWEET_LEN = 280
TWEET_COUNT = 4


@dataclass
class DraftTweet:
    text: str
    based_on: str
    format: str

    def to_dict(self) -> dict:
        return {"text": self.text, "based_on": self.based_on, "format": self.format}


class DraftValidationError(ValueError):
    """Raised when the model output can't be turned into 4 valid tweets."""


def _strip_fences(s: str) -> str:
    s = s.strip()
    # Sometimes the model wraps the whole thing in ```json ... ```
    return _FENCE.sub("", s).strip()


def _parse_json(raw: str) -> dict:
    cleaned = _strip_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Try to recover a JSON object substring if there's extra preamble.
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if not m:
            raise DraftValidationError(f"output is not JSON: {e}") from e
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError as e2:
            raise DraftValidationError(f"output is not JSON: {e2}") from e2


def parse_and_validate(raw: str, posted_hashes: set[str] | None = None) -> List[DraftTweet]:
    """Parse the model output into validated DraftTweet objects.

    Raises DraftValidationError on any rule violation. Hard rules:
    - Output is a JSON object with a "tweets" array.
    - Exactly 4 tweets.
    - Each tweet text is non-empty and <= 280 chars.
    - No URLs / no "http" / no "www" anywhere in the text.
    - No exact duplicate of anything in posted_hashes.
    """
    posted_hashes = posted_hashes or set()
    data = _parse_json(raw)
    if not isinstance(data, dict) or "tweets" not in data:
        raise DraftValidationError("missing top-level 'tweets' array")
    tweets_raw = data["tweets"]
    if not isinstance(tweets_raw, list):
        raise DraftValidationError("'tweets' must be a list")
    if len(tweets_raw) != TWEET_COUNT:
        raise DraftValidationError(f"expected {TWEET_COUNT} tweets, got {len(tweets_raw)}")

    out: list[DraftTweet] = []
    seen_texts: set[str] = set()
    for i, t in enumerate(tweets_raw):
        if not isinstance(t, dict):
            raise DraftValidationError(f"tweet #{i+1} is not an object")
        text = (t.get("text") or "").strip()
        based_on = (t.get("based_on") or "").strip()
        fmt = (t.get("format") or "").strip()
        if not text:
            raise DraftValidationError(f"tweet #{i+1} has empty text")
        if len(text) > MAX_TWEET_LEN:
            raise DraftValidationError(
                f"tweet #{i+1} is {len(text)} chars (max {MAX_TWEET_LEN}): {text!r}"
            )
        if _URL_HINT.search(text):
            raise DraftValidationError(f"tweet #{i+1} contains a URL/link: {text!r}")
        h = _hash_text(text)
        if h in posted_hashes:
            raise DraftValidationError(f"tweet #{i+1} duplicates a previously posted tweet")
        if h in seen_texts:
            raise DraftValidationError(f"tweet #{i+1} duplicates another tweet in this batch")
        seen_texts.add(h)
        out.append(DraftTweet(text=text, based_on=based_on, format=fmt))
    return out


def _hash_text(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()
