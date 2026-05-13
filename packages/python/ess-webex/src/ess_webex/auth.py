"""OAuth token management for the ess-webex CLI.

Handles the authorization code flow, token caching, and automatic refresh.
Tokens are cached at ~/.cache/ess-webex/token.json.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from ess_dirs import write_secure

TOKEN_CACHE = os.path.expanduser("~/.cache/ess-webex/token.json")
AUTHORIZE_URL = "https://webexapis.com/v1/authorize"
TOKEN_URL = "https://webexapis.com/v1/access_token"
REDIRECT_URI = "http://localhost:3030/callback"
REFRESH_MARGIN_SECS = 120

SCOPES = " ".join(
    [
        "spark:rooms_read",
        "spark:messages_read",
        "spark:messages_write",
        "meeting:schedules_read",
        "meeting:schedules_write",
        "spark:people_read",
    ]
)


class WebexOAuthError(Exception):
    """Raised when OAuth authentication fails."""


def _load_cache() -> dict | None:
    """Load cached token data from disk."""
    if not os.path.exists(TOKEN_CACHE):
        return None
    with open(TOKEN_CACHE) as f:
        return json.load(f)


def _save_cache(data: dict) -> None:
    """Persist token data to disk with restrictive permissions."""
    write_secure(TOKEN_CACHE, json.dumps(data, indent=2))


def _is_expired(data: dict) -> bool:
    """Check if the cached access token is expired or about to expire."""
    expires_at = data.get("expires_at", 0)
    return time.time() > (expires_at - REFRESH_MARGIN_SECS)


def _refresh_token(data: dict) -> dict:
    """Use the refresh token to get a new access token."""
    client_id = os.environ.get("WEBEX_CLIENT_ID", "")
    client_secret = os.environ.get("WEBEX_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        msg = "WEBEX_CLIENT_ID and WEBEX_CLIENT_SECRET required for refresh"
        raise WebexOAuthError(msg)

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": data["refresh_token"],
        },
        timeout=30,
    )
    if resp.status_code != 200:  # noqa: PLR2004
        msg = f"Token refresh failed: {resp.text}"
        raise WebexOAuthError(msg)

    token_data = resp.json()
    token_data["expires_at"] = time.time() + token_data.get("expires_in", 43200)
    _save_cache(token_data)
    return token_data


def get_access_token() -> str:
    """Get a valid access token, refreshing if needed.

    Priority:
    1. WEBEX_ACCESS_TOKEN env var (manual/personal token)
    2. Cached OAuth token (auto-refreshed)
    """
    env_token = os.environ.get("WEBEX_ACCESS_TOKEN")
    if env_token:
        return env_token

    cached = _load_cache()
    if cached is None:
        msg = (
            "No Webex token found. Run 'ess-webex login' to authenticate, "
            "or set WEBEX_ACCESS_TOKEN in your environment."
        )
        raise WebexOAuthError(msg)

    if _is_expired(cached):
        cached = _refresh_token(cached)

    return cached["access_token"]


def login() -> str:
    """Run the OAuth authorization code flow.

    Opens a browser for the user to authorize, captures the callback
    on a local HTTP server, exchanges the code for tokens.
    """
    client_id = os.environ.get("WEBEX_CLIENT_ID", "")
    client_secret = os.environ.get("WEBEX_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        msg = "Set WEBEX_CLIENT_ID and WEBEX_CLIENT_SECRET in .env"
        raise WebexOAuthError(msg)

    # Random state token to prevent OAuth CSRF attacks.
    state = secrets.token_urlsafe(32)

    params = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "state": state,
        }
    )
    auth_url = f"{AUTHORIZE_URL}?{params}"

    auth_code = None
    state_valid = False

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 -- name required by BaseHTTPRequestHandler
            nonlocal auth_code, state_valid
            query = parse_qs(urlparse(self.path).query)
            returned_state = query.get("state", [None])[0]
            state_valid = returned_state == state
            auth_code = query.get("code", [None])[0]
            self.send_response(200)  # noqa: PLR2004
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Authenticated! You can close this tab.</h2>")

        def log_message(self, format, *args):  # noqa: A002
            pass

    print(  # noqa: T201
        "Opening browser for Webex authorization...",
        file=sys.stderr,
    )
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 3030), CallbackHandler)  # noqa: S104
    try:
        server.handle_request()
    finally:
        server.server_close()

    if not auth_code:
        msg = "No authorization code received"
        raise WebexOAuthError(msg)

    if not state_valid:
        msg = "OAuth state mismatch -- possible CSRF attack"
        raise WebexOAuthError(msg)

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30,
    )
    if resp.status_code != 200:  # noqa: PLR2004
        msg = f"Token exchange failed: {resp.text}"
        raise WebexOAuthError(msg)

    token_data = resp.json()
    token_data["expires_at"] = time.time() + token_data.get("expires_in", 43200)
    _save_cache(token_data)

    print("Authenticated successfully.", file=sys.stderr)  # noqa: T201
    return token_data["access_token"]
