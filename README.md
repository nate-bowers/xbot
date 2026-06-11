# tweetbot

> Four tweets a day. Zero hands.

Reads the firehose, ranks the signal, drafts on a Claude Max subscription, posts via a GitHub Actions cron. Costs about four cents a day.

## How it runs

```
   morning                 mid-morning              afternoon and evening

   08:00 UTC               09 to 12 UTC             16:07, 20:13,
   GH Actions              Cowork task              00:19, 04:23 UTC
                                                    (next UTC day for the
   ingest + rank           drafts 4 tweets          last two)
   write prompt            push to xbot-state
                                                    GH Actions
                                                    posts one tweet per slot
```

## The split

This repo holds the code. Tweet state lives in a private sibling.

```
   xbot (public)                  xbot-state (private)

     src/                            queue.json
     config.yaml                     posted_log.json
     workflows/                      evergreen.json
     prompt_input.txt

         ──────  read  ─────▶
         ◀───── write  ──────
```

State is hydrated at the start of every workflow run and pushed back when the run finishes. The public repo never sees a tweet body in its history.

## Pipeline

```
   1. ingest    HN front page, arXiv, Google News queries, RSS feeds
   2. rank      cross-source dedup, freshness decay, weighted signal
   3. draft     Claude reads the prompt, writes 4 tweets as JSON
   4. validate  count, 280 char limit, no URLs, no posted duplicates
   5. post      4x daily, X v2 API
   6. fallback  if queue is empty, draw a random evergreen line
```

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
git clone https://github.com/nate-bowers/xbot-state.git data   # state is private

python -m src.cli ingest                     # try the ingestor
python -m src.cli rank --top 20              # today's ranked candidates
python -m src.cli draft-prompt --top 20      # the rendered Cowork prompt
DRY_RUN=true python -m src.cli post-next     # dry-run the post path
```

## Configuration

Everything tunable lives in `config.yaml`: which sources are enabled, HN score thresholds, arXiv categories, Google News queries, the RSS list, freshness half-life, source weights, the dedup threshold, and the four UTC posting slots. The approved @mentions list lives there too.

Secrets never go in `config.yaml`. They come from `.env` locally or GitHub Actions secrets in CI. See `.env.example`.

## Layout

```
src/
  ingest/    schema, HN, arXiv, Google News, RSS, collector
  rank/      dedup, score, rank
  generate/  prompt template, JSON validator
  post/      queue, evergreen, X v2 client, cron entrypoint
  notify/    Telegram pings
  cli.py     ingest, rank, draft-prompt, draft-commit, queue-show, post-next

.github/workflows/
  ci.yml                pytest on every push
  generate-input.yml    daily ingest + rank
  post.yml              4x daily posting cron

config.yaml             every tunable, no secrets
.env.example            required env vars
COWORK_TASK_PROMPT.md   what to paste into the daily Cowork task
```

## Stack

| Layer        | Choice                       |
|:-------------|:-----------------------------|
| Language     | Python 3.12                  |
| HTTP         | requests                     |
| Dedup        | rapidfuzz                    |
| Config       | yaml                         |
| Test         | pytest, 36 passing           |
| Runtime      | GitHub Actions               |
| X auth       | OAuth 1.0a or OAuth 2.0      |
| Drafting     | Claude Max via Cowork        |
| Alerting     | Telegram bot (optional)      |

## Cost

| Item              | Cost                          |
|:------------------|:------------------------------|
| Generation        | $0 (Claude Max)               |
| Cron and runners  | $0 (Actions, public repo)     |
| Per post          | about $0.01 (X)               |
| Daily             | about $0.04                   |
| Monthly           | about $1.20                   |

## Status

Live. First scheduled post fired 2026-06-11. The cron is wired, the queue refills daily, the evergreen pool catches misses.
