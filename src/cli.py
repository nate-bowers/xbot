"""Local CLI for the tweetbot.

Commands:
    python -m src.cli ingest                run all ingest clients
    python -m src.cli rank [--top N]        ingest + dedup + score + top-N
    python -m src.cli draft-prompt          print the rendered generation prompt
    python -m src.cli draft-commit <file>   validate model JSON output, write queue.json
    python -m src.cli queue-show            print the current queue
    python -m src.cli post-next             run the cron entrypoint (respects DRY_RUN)

Imports are intentionally deferred per-command so commands that don't need
the ingest pipeline (draft-commit, queue-show) work with stock Python,
no pip install required. The Cowork task only ever runs draft-commit, so
keeping it dep-free means Cowork's sandbox doesn't need network access.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def _load_config(path: str) -> dict:
    import yaml  # heavy import deferred
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"config not found: {path}")
    with p.open() as f:
        return yaml.safe_load(f) or {}


def _print_table(items, show_score: bool = False) -> None:
    if not items:
        print("(no items)")
        return
    print("#  source  age_h  raw  " + ("final  " if show_score else "") + "title")
    print("-" * 100)
    now = datetime.utcnow()
    for i, it in enumerate(items, 1):
        age = f"{it.age_hours(now):6.1f}"
        raw = f"{it.score:7.1f}"
        title = it.title.replace("\n", " ")
        if len(title) > 80:
            title = title[:77] + "..."
        if show_score:
            final = it.extra.get("score_breakdown", {}).get("final", 0.0)
            print(f"{i:3d}  {it.source:20.20}  {age}  {raw}  {final:6.4f}  {title}")
        else:
            print(f"{i:3d}  {it.source:20.20}  {age}  {raw}  {title}")


def cmd_ingest(args) -> int:
    from .ingest.collect import collect  # heavy, network
    config = _load_config(args.config)
    items = collect(config)
    print()
    _print_table(items)
    return 0


def cmd_rank(args) -> int:
    from .ingest.collect import collect
    from .rank.rank import rank as rank_items
    config = _load_config(args.config)
    items = collect(config)
    top = rank_items(items, config.get("rank", {}) or {}, n=args.top)
    print()
    print(f"Top {len(top)} after dedup + scoring:")
    _print_table(top, show_score=True)
    return 0


def cmd_draft_prompt(args) -> int:
    from .ingest.collect import collect
    from .rank.rank import rank as rank_items
    from .generate.prompt import build_prompt
    config = _load_config(args.config)
    items = collect(config)
    top = rank_items(items, config.get("rank", {}) or {}, n=args.top)
    mentions = config.get("approved_mentions", []) or []
    sys.stderr.write(
        f"[draft-prompt] using top {len(top)} items, {len(mentions)} approved handles\n"
    )
    print(build_prompt(top, approved_mentions=mentions))
    return 0


def cmd_draft_commit(args) -> int:
    # The hot path for Cowork. Deliberately depends on nothing outside stdlib +
    # our pure-Python modules.
    from .generate.draft import DraftValidationError, parse_and_validate
    from .post import queue as queue_mod
    raw = Path(args.file).read_text() if args.file != "-" else sys.stdin.read()
    posted = queue_mod.posted_hashes()
    try:
        drafts = parse_and_validate(raw, posted_hashes=posted)
    except DraftValidationError as e:
        print(f"[draft-commit] validation failed: {e}", file=sys.stderr)
        return 2
    queue = queue_mod.write_queue_from_drafts([d.to_dict() for d in drafts])
    print(f"[draft-commit] wrote {len(queue['tweets'])} tweets to data/queue.json")
    for t in queue["tweets"]:
        print(f"  - ({len(t['text'])} chars) {t['text']}")
    return 0


def cmd_queue_show(args) -> int:
    from .post import queue as queue_mod
    queue = queue_mod.load_queue()
    print(json.dumps(queue, indent=2))
    return 0


def cmd_post_next(args) -> int:
    from .post import post_next as post_next_mod
    return post_next_mod.main()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tweetbot")
    parser.add_argument("--config", default="config.yaml", help="path to config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ingest", help="run all ingest clients and print everything collected")

    p_rank = sub.add_parser("rank", help="ingest then print the ranked top-N")
    p_rank.add_argument("--top", type=int, default=None, help="override top_n from config")

    p_dp = sub.add_parser("draft-prompt", help="print the rendered generation prompt")
    p_dp.add_argument("--top", type=int, default=None, help="override top_n from config")

    p_dc = sub.add_parser(
        "draft-commit",
        help="validate model output JSON and write data/queue.json",
    )
    p_dc.add_argument("file", help="path to JSON file (use '-' for stdin)")

    sub.add_parser("queue-show", help="print data/queue.json as JSON")

    sub.add_parser("post-next", help="post the next queued tweet (respects DRY_RUN)")

    args = parser.parse_args(argv)
    dispatch = {
        "ingest": cmd_ingest,
        "rank": cmd_rank,
        "draft-prompt": cmd_draft_prompt,
        "draft-commit": cmd_draft_commit,
        "queue-show": cmd_queue_show,
        "post-next": cmd_post_next,
    }
    fn = dispatch.get(args.cmd)
    if not fn:
        parser.error(f"unknown command {args.cmd}")
        return 2
    return fn(args)


if __name__ == "__main__":
    sys.exit(main())
