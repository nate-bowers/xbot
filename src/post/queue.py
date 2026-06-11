"""Persistent queue + posted-log on disk. Both live in data/ and get committed."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


QUEUE_PATH = Path("data/queue.json")
POSTED_LOG_PATH = Path("data/posted_log.json")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()


def load_queue(path: Path = QUEUE_PATH) -> dict:
    if not path.exists():
        return {"generated_at": None, "tweets": []}
    with path.open() as f:
        return json.load(f)


def save_queue(queue: dict, path: Path = QUEUE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(queue, f, indent=2)
        f.write("\n")


def load_posted_log(path: Path = POSTED_LOG_PATH) -> dict:
    if not path.exists():
        return {"hashes": [], "entries": []}
    with path.open() as f:
        return json.load(f)


def save_posted_log(log: dict, path: Path = POSTED_LOG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(log, f, indent=2)
        f.write("\n")


def posted_hashes(log: Optional[dict] = None) -> set[str]:
    log = log if log is not None else load_posted_log()
    return set(log.get("hashes", []))


def write_queue_from_drafts(drafts: Iterable[dict]) -> dict:
    """Build a fresh queue from validated draft tweets and persist it."""
    queue = {
        "generated_at": _utcnow_iso(),
        "tweets": [
            {
                "id": str(uuid.uuid4()),
                "text": d["text"],
                "based_on": d.get("based_on", ""),
                "format": d.get("format", ""),
                "posted": False,
                "posted_at": None,
                "tweet_id": None,
            }
            for d in drafts
        ],
    }
    save_queue(queue)
    return queue


def next_unposted(queue: Optional[dict] = None) -> Optional[dict]:
    queue = queue if queue is not None else load_queue()
    for t in queue.get("tweets", []):
        if not t.get("posted"):
            return t
    return None


def mark_posted(queue_entry_id: str, tweet_id: str) -> None:
    """Mark a queue entry as posted and record it in the posted log."""
    queue = load_queue()
    text = _text_for_entry(queue, queue_entry_id)
    for t in queue.get("tweets", []):
        if t["id"] == queue_entry_id:
            t["posted"] = True
            t["posted_at"] = _utcnow_iso()
            t["tweet_id"] = tweet_id
            break
    save_queue(queue)
    record_posted(text, tweet_id, source="queue", entry_id=queue_entry_id)


def record_posted(text: str, tweet_id: str, source: str = "queue", entry_id: str = "") -> None:
    """Append to posted_log.json. Used directly for evergreen posts, which
    don't have a corresponding queue entry to mark."""
    log = load_posted_log()
    h = _hash_text(text)
    if h not in log["hashes"]:
        log["hashes"].append(h)
    log["entries"].append(
        {
            "id": entry_id,
            "tweet_id": tweet_id,
            "posted_at": _utcnow_iso(),
            "source": source,
        }
    )
    save_posted_log(log)


def _text_for_entry(queue: dict, entry_id: str) -> str:
    for t in queue.get("tweets", []):
        if t["id"] == entry_id:
            return t["text"]
    return ""
