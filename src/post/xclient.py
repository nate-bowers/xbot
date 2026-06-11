"""X API v2 write client. Posts to /2/tweets. OAuth 1.0a user context by default;
OAuth 2.0 bearer is supported by setting X_AUTH_TYPE=oauth2 and X_BEARER_TOKEN.

Credentials come from environment only — never hardcoded, never committed."""
from __future__ import annotations

import os
from typing import Optional

import requests
from requests_oauthlib import OAuth1


_TWEETS_URL = "https://api.twitter.com/2/tweets"
_TIMEOUT = 20


class XPostError(RuntimeError):
    def __init__(self, message: str, status: Optional[int] = None, code: Optional[int] = None):
        super().__init__(message)
        self.status = status
        self.code = code


def _oauth1_from_env() -> OAuth1:
    required = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise XPostError(f"OAuth1 env missing: {', '.join(missing)}")
    return OAuth1(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_SECRET"],
        signature_type="auth_header",
    )


def _oauth2_headers_from_env() -> dict:
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        raise XPostError("OAuth2 env missing: X_BEARER_TOKEN")
    return {"Authorization": f"Bearer {token}"}


def post_tweet(text: str) -> str:
    """POST /2/tweets with {text}. Returns the new tweet's id string."""
    auth_type = (os.environ.get("X_AUTH_TYPE") or "oauth1").lower()
    body = {"text": text}

    if auth_type == "oauth2":
        headers = {**_oauth2_headers_from_env(), "Content-Type": "application/json"}
        resp = requests.post(_TWEETS_URL, json=body, headers=headers, timeout=_TIMEOUT)
    else:
        auth = _oauth1_from_env()
        resp = requests.post(_TWEETS_URL, json=body, auth=auth, timeout=_TIMEOUT)

    if resp.status_code >= 400:
        code = None
        try:
            payload = resp.json()
            # X surfaces an `errors` array with a numeric code we want to forward
            # (187 dup, 429 rate, 403 policy, etc).
            if isinstance(payload, dict):
                errs = payload.get("errors") or []
                if errs and isinstance(errs, list):
                    code = errs[0].get("code")
                detail = payload
            else:
                detail = resp.text
        except Exception:
            detail = resp.text
        raise XPostError(
            f"X API {resp.status_code}: {detail}", status=resp.status_code, code=code
        )

    data = resp.json()
    tweet_id = ((data or {}).get("data") or {}).get("id")
    if not tweet_id:
        raise XPostError(f"X API success but no tweet id in response: {data}")
    return str(tweet_id)
