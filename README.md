# tweetbot

Automated bot that posts ~4 high-signal tech/AI tweets per day. Generation is
free (runs on a Claude Cowork scheduled task / the user's Max subscription);
posting is a free GitHub Actions cron. The only paid call is the X write itself
(~$0.01/post).

See `CLAUDE_HANDOFF.md` for the full architecture and design principles.

## Status

- **Phase 1 (ingestion)** — built. HN, arXiv, Google News, generic RSS.
- **Phase 2 (rank/dedup)** — built. Cross-source dedup, freshness + signal
  scoring, configurable source weights.
- **Phase 3 (generation)** — built. Prompt template + JSON parser/validator.
  Drafting runs on your Max subscription via the Cowork task — there is
  intentionally no Anthropic API key path.
- **Phase 4 (posting)** — built. Queue, X v2 client (OAuth 1.0a + OAuth 2.0),
  `post-next` cron entrypoint with `DRY_RUN` switch, GitHub Actions workflow,
  Telegram failure ping.
- **Phase 5 (go-live)** — pending user actions: add X secrets to GH, set up the
  Cowork task, review the first queue, flip `DRY_RUN` to `false`.

## Quickstart (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Phase 1 — verify ingestion
python -m src.cli ingest

# Phase 2 — verify ranking
python -m src.cli rank --top 20

# Phase 3 — see the rendered prompt your daily Cowork task will use
python -m src.cli draft-prompt --top 20 > /tmp/tweetbot_prompt.txt
cat /tmp/tweetbot_prompt.txt

# Phase 3 — feed validated JSON back in (Cowork does this in production)
python -m src.cli draft-commit /tmp/tweetbot_output.json

# Phase 4 — dry-run the posting cron
python -m src.cli queue-show
DRY_RUN=true python -m src.cli post-next
```

## Config

`config.yaml` holds every tunable: enabled sources, HN thresholds, arXiv
categories, Google News queries, the RSS feed list, freshness half-life,
weights, dedup threshold, and posting slots (UTC).

`config.yaml` does **not** contain secrets. Secrets only ever come from `.env`
locally or GitHub Actions secrets in CI. See `.env.example`.

## Layout

```
src/
  ingest/    Item schema + HN / arXiv / Google News / generic RSS + collector
  rank/      dedup, score, rank
  generate/  prompt template, parse/validate model output
  post/      queue.json + posted_log.json, X v2 client, cron entrypoint
  notify/    Telegram pings
  cli.py     ingest | rank | draft-prompt | draft-commit | queue-show | post-next
data/        runtime artifacts (queue.json, posted_log.json) — committed
.github/workflows/post.yml   the free posting cron
COWORK_TASK_PROMPT.md        what to paste into the daily Cowork task
config.yaml                  all tunables
.env.example                 documents required env vars
```

## Production runtime model

- **Daily Cowork task** runs the prompt in `COWORK_TASK_PROMPT.md`. It calls
  `draft-prompt`, drafts 4 tweets in JSON inline, calls `draft-commit`, and
  pushes the updated `data/queue.json`.
- **GitHub Actions cron** (`post.yml`) fires 4× per day on UTC times that
  approximate 9am / 12pm / 3pm / 7pm ET. Each run takes the next unposted
  queue entry, posts (or dry-run-logs) it, marks it posted, commits
  `data/queue.json` + `data/posted_log.json` with `[skip ci]`.

## Secrets the user adds

In GitHub repo settings → Secrets and variables → Actions:

**Repository variables** (not secrets):
- `DRY_RUN` — set to `false` to go live. Default and any other value = dry-run.
- `X_AUTH_TYPE` — `oauth1` (default) or `oauth2`.

**Secrets** (OAuth 1.0a user context, the default):
- `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET`

**Secrets** (OAuth 2.0 user context, alternative):
- `X_BEARER_TOKEN`

**Secrets** (optional):
- `TG_BOT_TOKEN`, `TG_CHAT_ID` — for failure pings and queue-ready heads-ups.

Locally, the same vars go in `.env` (which is gitignored).

## Go-live checklist

1. Phase 1 ingest verified locally — `python -m src.cli ingest`.
2. Phase 2 ranked output looks sane — `python -m src.cli rank`.
3. Cowork task runs and produces a good `data/queue.json` — `queue-show`.
4. Reviewed a full day's queue by hand: accurate, on-voice, link-free.
5. X secrets added; one `workflow_dispatch` run shows the right "would post"
   logs.
6. Flip `DRY_RUN` to `false`. Watch the first live post.

## What stays the user's job

- X dev account, OAuth tokens, pay-per-use billing.
- GitHub repo secrets / variables.
- Setting up the Cowork scheduled task.
- Reviewing the first queue and flipping `DRY_RUN`.
