"""Cron entrypoint. Picks the next unposted queue entry (or, if the queue
is empty, a random evergreen entry), posts it (or logs in dry-run), updates
state, pings telegram on success and failure.

Run: `python -m src.post.post_next`
"""
from __future__ import annotations

import os
import sys

from ..notify import telegram
from . import evergreen
from . import queue as q
from .xclient import XPostError, post_tweet


def _is_dry_run() -> bool:
    val = os.environ.get("DRY_RUN", "true").strip().lower()
    # Default to dry-run unless explicitly disabled. "false" / "0" / "no" / "off"
    # all turn it off; everything else stays safe.
    return val not in {"false", "0", "no", "off"}


def main() -> int:
    entry = q.next_unposted()
    text = None
    is_evergreen = False
    if entry:
        text = entry["text"]
    else:
        # Daily queue is empty (Cowork didn't run or all 4 posted). Peek at
        # a random evergreen entry — we'll only remove it from the pool after
        # the post actually succeeds, so dry-runs and post failures don't
        # burn an evergreen line.
        text = evergreen.peek_random()
        if not text:
            print("[post_next] queue and evergreen pool both empty; nothing to do")
            return 0
        is_evergreen = True
        print(f"[post_next] queue empty — picked from evergreen ({evergreen.remaining()} in pool)")

    # Belt-and-suspenders dedupe against posted_log, for either path.
    posted_set = q.posted_hashes()
    text_hash = q._hash_text(text)
    if text_hash in posted_set:
        src = "evergreen" if is_evergreen else "queue"
        print(f"[post_next] text already in posted_log; skipping (source={src})")
        if not is_evergreen:
            q.mark_posted(entry["id"], tweet_id="DEDUPED")
        return 0

    if _is_dry_run():
        src = "evergreen" if is_evergreen else "queue"
        print(f"[post_next] DRY_RUN — would post ({src}): {text!r}")
        return 0

    try:
        tweet_id = post_tweet(text)
    except XPostError as e:
        msg = f"[post_next] X post failed (code={e.code} status={e.status}): {e}"
        print(msg, file=sys.stderr)
        telegram.send(f"tweetbot: post failed — {e}")
        return 1
    except Exception as e:
        print(f"[post_next] unexpected error: {e}", file=sys.stderr)
        telegram.send(f"tweetbot: unexpected error — {e}")
        return 1

    if is_evergreen:
        # Post succeeded — NOW remove the entry from the evergreen pool, so
        # post failures (handled above) leave the pool intact for next time.
        evergreen.remove(text)
        q.record_posted(text, tweet_id=tweet_id, source="evergreen")
    else:
        q.mark_posted(entry["id"], tweet_id=tweet_id)

    print(f"[post_next] posted tweet id={tweet_id}: {text!r}")
    telegram.send(
        f"tweet posted ✅\n{text}\n\n"
        f"https://x.com/i/web/status/{tweet_id}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
