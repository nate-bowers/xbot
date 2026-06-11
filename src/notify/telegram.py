"""Telegram failure/heads-up pings. Credentials from env."""
from __future__ import annotations

import os

import requests


_API = "https://api.telegram.org"
_TIMEOUT = 10


def send(message: str) -> bool:
    """Best-effort send. Returns True on success; logs and returns False on failure.

    Never raises — notifications must not break the cron run that called them.
    """
    token = os.environ.get("TG_BOT_TOKEN")
    chat = os.environ.get("TG_CHAT_ID")
    if not token or not chat:
        print(f"[telegram] skipped (no TG_BOT_TOKEN/TG_CHAT_ID): {message}")
        return False
    try:
        r = requests.post(
            f"{_API}/bot{token}/sendMessage",
            json={"chat_id": chat, "text": message, "disable_web_page_preview": True},
            timeout=_TIMEOUT,
        )
        if r.status_code >= 400:
            print(f"[telegram] send failed {r.status_code}: {r.text}")
            return False
        return True
    except Exception as e:
        print(f"[telegram] send error: {e}")
        return False
