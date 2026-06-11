# Cowork daily task prompt — tweetbot queue generation

Paste this into the Claude Cowork scheduled task. Runs once daily on the
user's Max subscription. Drafting runs ON your Max subscription — no
Anthropic API key, no SDK, no external generation API.

## Architecture (read once)

- Two repos: **`nate-bowers/xbot`** is public and holds the code +
  `data/prompt_input.txt` (rendered by the morning GH Action).
  **`nate-bowers/xbot-state`** is private and holds the tweet state files
  (`queue.json`, `posted_log.json`, `evergreen.json`).
- A separate GitHub Actions cron runs ingest+rank every morning at 08:00 UTC
  on GitHub's free runners (full internet access) and commits
  `data/prompt_input.txt` to the public xbot repo. That file is the entire
  rendered prompt — story list, voice rules, approved handles, everything.
- Your only job: pull xbot, read `prompt_input.txt`, draft 4 tweets as JSON,
  validate, push `queue.json` to **xbot-state** (not xbot).
- `draft-commit` has been refactored to need **zero external Python deps**.
  Stock `python3` in the sandbox is enough — no `pip install`, no venv.
  This sidesteps the sandbox's network restrictions entirely.

## Required: PAT in .env

The PAT lives in `.env` in the repo (gitignored, never committed). The task
sources it at startup. If `.env` is missing or doesn't contain `GH_TOKEN=...`,
the task stops — do not try to push without it.

User setup (one time): from the Mac terminal,
```
echo 'GH_TOKEN=github_pat_PASTE_HERE' >> ~/Documents/Claude/xbot/.env
chmod 600 ~/Documents/Claude/xbot/.env
```

---

## Task prompt (copy from here, paste into Cowork)

You are the daily generator for the user's tweetbot. The repo lives on the
host at `~/Documents/Claude/xbot` but your bash tool runs in an isolated Linux
sandbox — the repo is reachable only at the mount path Cowork returns for
this session.

Execution rules:
- All drafting runs on the Max subscription. Do NOT call any Anthropic API,
  SDK, or external generation API. If a step seems to need one, STOP and
  tell the user.
- Don't run ingest yourself or web-search for stories. The GitHub Action
  is the source of truth — if `data/prompt_input.txt` is missing or stale
  (>24h old), STOP and tell the user instead of falling back.
- Don't invent or hardcode credentials. The PAT comes from `.env` only.

Steps, in order. Stop on the first unrecoverable error.

1. **Mount the repo.** Call `mcp__cowork__request_cowork_directory` with
   path `~/Documents/Claude/xbot`. Capture the bash mount path it returns (looks
   like `/sessions/<session-id>/mnt/xbot`). Store it in `REPO`:
   ```
   REPO=<mount path returned by the tool>
   cd "$REPO"
   ```

2. **Sanity checks + load secrets.**
   ```
   test -d "$REPO/.git" && test -f "$REPO/config.yaml" || \
     { echo "ERROR: repo not mounted correctly"; exit 2; }
   test -f "$REPO/.env" || \
     { echo "ERROR: $REPO/.env missing. User must create it with GH_TOKEN=..."; exit 2; }
   set -a; source "$REPO/.env"; set +a
   test -n "$GH_TOKEN" || \
     { echo "ERROR: GH_TOKEN not set in .env"; exit 2; }
   ```

3. **Pull latest xbot (for code + today's `prompt_input.txt`):**
   ```
   git pull --rebase https://x-access-token:$GH_TOKEN@github.com/nate-bowers/xbot.git main
   ```

4. **Verify today's prompt input exists and is recent:**
   ```
   test -f data/prompt_input.txt && [ "$(find data/prompt_input.txt -mmin -1440)" ] || \
     { echo "ERROR: data/prompt_input.txt missing or older than 24h. Check the generate-input GH Action."; exit 2; }
   ```

5. **Hydrate the existing state from the private xbot-state repo:**
   ```
   git clone --depth=1 https://x-access-token:$GH_TOKEN@github.com/nate-bowers/xbot-state.git /tmp/xbot-state
   cp /tmp/xbot-state/queue.json /tmp/xbot-state/posted_log.json /tmp/xbot-state/evergreen.json data/
   ```

6. **Read `data/prompt_input.txt` in full.** It contains the full
   instructions (voice rules, hard stops, approved handles) and the ranked
   story list. Follow those instructions and produce ONLY the JSON object
   specified at the end (no preamble, no markdown fences).

7. **Write the JSON to `/tmp/tweetbot_output.json`.**

8. **Validate and write the queue (writes data/queue.json locally):**
   ```
   python3 -m src.cli draft-commit /tmp/tweetbot_output.json
   ```
   `draft-commit` uses only stdlib — stock python3 works, no venv needed.
   If validation fails (wrong count, too long, URL detected, duplicate),
   redo step 6 fixing the specific issue it called out, then retry.

9. **Push the new queue to the private xbot-state repo** (NOT xbot — state
   never gets committed to the public repo):
   ```
   cp data/queue.json /tmp/xbot-state/queue.json
   cd /tmp/xbot-state
   git -c user.name="tweetbot" -c user.email="tweetbot@local" \
       commit -am "queue: regenerate $(date -u +%Y-%m-%d)" --allow-empty
   git push https://x-access-token:$GH_TOKEN@github.com/nate-bowers/xbot-state.git main
   cd "$REPO"
   ```

10. **(Optional) Heads-up ping.** If `TG_BOT_TOKEN` and `TG_CHAT_ID` are in
    `.env` (they're already in the GH secrets but you can also drop them into
    .env if you want this step), ping:
    ```
    python3 -c "from src.notify import telegram; telegram.send('tweetbot: queue ready, 4 tweets')"
    ```

On success, report how many tweets were queued and confirm the push.

If anything aborts, summarize what failed in one short paragraph and stop.

---

## Schedule

- Once per day, between **09:00 UTC and 12:00 UTC** (after the GH Action at
  08:00 UTC writes `prompt_input.txt`, before the first posting slot at
  13:00 UTC).
- On Max (15 scheduled runs/day), this uses 1 run.

## PAT setup (one time)

1. Visit https://github.com/settings/personal-access-tokens/new (fine-grained).
2. **Token name**: `tweetbot-cowork-push`
3. **Repository access**: "Only select repositories" → select BOTH
   `nate-bowers/xbot` and `nate-bowers/xbot-state`.
4. **Permissions → Repository permissions → Contents: Read and write**.
   Leave everything else as "No access".
5. **Expiration**: 90 days or longer. Set a calendar reminder to rotate.
6. Generate, copy the `github_pat_...` string.
7. From the Mac terminal:
   ```
   echo 'GH_TOKEN=github_pat_PASTE_HERE' >> ~/Documents/Claude/xbot/.env
   chmod 600 ~/Documents/Claude/xbot/.env
   ```
   `.env` is gitignored — never reaches GitHub. Cowork reads it because
   it has folder access; the sandbox sources it at startup.
