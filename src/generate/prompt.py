"""The generation prompt. Filled with ranked items + the approved handle list
by `build_prompt`."""
from __future__ import annotations

from typing import Iterable, Sequence

from ..ingest.schema import Item


_PROMPT_TEMPLATE = """You are drafting tweets for a tech/AI audience ("tech twitter"). Below are the
top current stories right now, ranked. Write 4 tweets, each about a DIFFERENT
story, chosen for highest viral/engagement potential.

Read every rule, every time.

CONTROVERSIAL / OPINIONATED
- Every tweet must be a clear opinion that picks a side. Lukewarm "on one hand,
  on the other" framings are banned. If a tweet wouldn't irritate at least
  10% of readers, the take isn't sharp enough.
- Be willing to be wrong out loud. Lean in. The goal is engagement, not
  consensus.

NOT A HEADLINE
- Never open with the news. Open with your reaction. "Google released X" is
  the headline; we want the take. Assume the reader either knows the news
  or gets hooked by the take alone.

INFORMAL VOICE
- lowercase is fine. sentence fragments fine. dropped words fine. contractions
  encouraged. should sound like a smart person typing fast on their phone,
  not a press release.
- Periods at the end of short lines are optional.
- BANNED phrases / markers (these scream "AI wrote this"):
  em-dashes (—), semicolons, "moreover", "in essence", "fundamentally",
  "it's worth noting", "the real story is", "make no mistake".

CALLOUTS (optional, high-value when natural)
- When the take is reacting to something a specific person said, decided, or
  shipped, tag them with @<handle>. Lands in their notifications and the
  notifications of everyone who follows them.
- ONLY use handles from the APPROVED HANDLES list below. Never guess a
  handle — wrong @ = wrong person notified = embarrassing.
- If the take is about someone NOT on the approved list, just describe them
  by name and don't tag.
- Max 1 @mention per tweet.

HASHTAGS
- 0-2 hashtags per tweet. Integrated into the prose where they read naturally
  ("...this is the year of #AGI"), NOT stacked at the end like SEO.
- Reasonable picks: #AI #AGI #LLM #startups #VC #crypto #web3 #YC #SaaS.
  Skip niche/obscure tags that nobody searches.

HARD STOPS (these are not preferences, they are deal-breakers)
- Each tweet under 280 characters total.
- NO URLs or links anywhere in the tweet text. Anything with http/https/www
  is rejected.
- No fabricated facts, quotes, or numbers. If you can't source the detail
  from the story, don't state it. Controversial takes need REAL numbers, not
  invented ones — invented stats get community-noted.

FORMAT VARIATION
- 4 tweets, 4 different angles. Don't ship two tweets in the same shape.
  e.g. one calling out a named person's specific decision, one contrarian
  framing of a headline everyone agreed on, one "everyone is wrong about X"
  framing, one sharp one-liner. Pick four distinct angles.

APPROVED HANDLES (use sparingly; only when reacting to something they did)
{approved_handles_block}

Stories:
{ranked_items_block}

Return ONLY valid JSON, no preamble, no markdown fences:
{{"tweets": [{{"text": "...", "based_on": "<story title>", "format": "<which format>"}}, ... x4]}}
"""


def _format_item(i: int, it: Item) -> str:
    age_h = it.age_hours()
    src = it.source
    bits = [f"{i}. [{src}] ({age_h:.1f}h old) {it.title}"]
    if it.summary:
        s = it.summary.replace("\n", " ").strip()
        if len(s) > 300:
            s = s[:297] + "..."
        bits.append(f"   summary: {s}")
    also = it.extra.get("also_seen_in") or []
    if also:
        bits.append(f"   also seen in: {', '.join(sorted({a['source'] for a in also}))}")
    return "\n".join(bits)


def _format_handle(entry: dict) -> str:
    handle = entry.get("handle", "").lstrip("@")
    name = entry.get("name", "")
    role = entry.get("role", "")
    bits = [f"- @{handle}"]
    if name:
        bits.append(f" — {name}")
    if role:
        bits.append(f" ({role})")
    return "".join(bits)


def build_prompt(items: Iterable[Item], approved_mentions: Sequence[dict] | None = None) -> str:
    items_block = "\n".join(_format_item(i, it) for i, it in enumerate(items, 1))
    handles = approved_mentions or []
    if handles:
        handles_block = "\n".join(_format_handle(h) for h in handles)
    else:
        handles_block = "(none configured; do not use any @mentions)"
    return _PROMPT_TEMPLATE.format(
        approved_handles_block=handles_block,
        ranked_items_block=items_block,
    )
