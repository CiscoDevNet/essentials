"""Microsoft Graph API client for Outlook email."""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import time
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus

import msal
import requests
from decouple import strtobool
from ess_dirs import write_secure

GRAPH_BASE = "https://graph.microsoft.com/v1.0/me"
TOKEN_CACHE = os.path.expanduser("~/.cache/ess-outlook/graph_token_cache.json")
SCOPES = ["Mail.ReadWrite"]

# Treat a token as spent this many seconds before its actual expiry, so a
# long-running command does not fail mid-flight.
_EXPIRY_BUFFER_SECONDS = 300

# Loopback port for the interactive flow. 0 lets MSAL pick any free port,
# which requires the app registration to list "http://localhost" as a redirect
# URI. Registrations without one fail with AADSTS50011, so the flow is opt-in
# via GRAPH_INTERACTIVE_AUTH rather than attempted by default.
_INTERACTIVE_REDIRECT_PORT = 0

# Cap the wait on the loopback redirect. Without this, a rejected redirect URI
# leaves the browser on an error page and MSAL listening forever.
_INTERACTIVE_TIMEOUT_SECONDS = 90

logger = logging.getLogger(__name__)


class GraphAuthError(Exception):
    """Raised when Graph API authentication fails."""


def _cast_bool(value: str) -> bool:
    """Coerce an environment value to a bool, tolerating stray whitespace.

    Uses decouple's vocabulary (``1``/``true``/``yes``/``y``/``on``/``t`` and
    their negatives) and raises ``ValueError`` on anything else, so a typo
    surfaces instead of silently leaving a flag off.
    """
    value = value.strip()
    return bool(strtobool(value)) if value else False


def _get_env(name: str) -> str:
    """Read a stripped environment value.

    Reads the process environment only. Populating it from a ``.env`` file is
    the entrypoint's job (``__main__.load_dotenv``), so importing this module
    never picks up configuration the caller did not supply.
    """
    return os.environ.get(name, "").strip()


def _parse_date(value: str) -> datetime:
    """Parse an ISO-8601 date string into a timezone-aware datetime."""
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _get_app() -> msal.PublicClientApplication:
    """Build an MSAL app using env vars for client/tenant."""
    client_id = _get_env("CLIENT_ID")
    tenant_id = _get_env("TENANT_ID")
    if not client_id or not tenant_id:
        msg = "CLIENT_ID and TENANT_ID must be set in environment or .env"
        raise GraphAuthError(msg)

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE):
        with open(TOKEN_CACHE) as f:
            cache.deserialize(f.read())

    return msal.PublicClientApplication(
        client_id, authority=authority, token_cache=cache
    )


def _save_cache(app: msal.PublicClientApplication) -> None:
    """Persist the MSAL token cache to disk with restrictive permissions."""
    cache = app.token_cache
    if cache.has_state_changed:
        write_secure(TOKEN_CACHE, cache.serialize())


def _is_token_expired(token: str) -> bool:
    """Report whether a JWT's ``exp`` claim has passed.

    Unparseable tokens are reported as expired so the caller falls back to a
    real sign-in rather than sending a malformed header.
    """
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError, binascii.Error, UnicodeDecodeError):
        return True

    expires_at = claims.get("exp")
    if expires_at is None:
        return True

    try:
        expires_at = int(expires_at)
    except (TypeError, ValueError):
        return True

    return time.time() > (expires_at - _EXPIRY_BUFFER_SECONDS)


def _get_supplied_token() -> str | None:
    """Return a usable ``GRAPH_ACCESS_TOKEN``, or None if absent or expired."""
    token = _get_env("GRAPH_ACCESS_TOKEN")
    if not token:
        return None

    if _is_token_expired(token):
        logger.warning(
            "GRAPH_ACCESS_TOKEN is expired or invalid; falling back to sign-in. "
            "Paste a fresh token to skip this."
        )
        os.environ.pop("GRAPH_ACCESS_TOKEN", None)
        return None

    return token


def _is_interactive_enabled() -> bool:
    """Report whether ``GRAPH_INTERACTIVE_AUTH`` opts in to browser sign-in."""
    return _cast_bool(_get_env("GRAPH_INTERACTIVE_AUTH"))


def _acquire_interactive(app: msal.PublicClientApplication) -> dict | None:
    """Sign in through the system browser via a loopback redirect.

    Preferred over the device-code flow: Conditional Access policies commonly
    block device code specifically, while allowing the same authorization-code
    grant from a browser on a managed device.

    Opt in with ``GRAPH_INTERACTIVE_AUTH``, which requires an app registration
    listing ``http://localhost`` as a redirect URI. Returns None when opted
    out, the browser is unreachable, or the user never completes sign-in,
    leaving device code as the fallback.
    """
    if not _is_interactive_enabled():
        logger.debug("Interactive sign-in not enabled; skipping")
        return None

    logger.info("Opening browser for Microsoft sign-in...")
    try:
        result = app.acquire_token_interactive(
            SCOPES,
            port=_INTERACTIVE_REDIRECT_PORT,
            timeout=_INTERACTIVE_TIMEOUT_SECONDS,
        )
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        logger.warning("Interactive sign-in failed; falling back to device code.")
        logger.debug("Interactive sign-in unavailable", exc_info=True)
        return None

    if result and "access_token" in result:
        return result

    logger.warning(
        "Interactive sign-in did not complete. If the browser showed "
        "AADSTS50011 (redirect URI mismatch), client %s has no "
        "'http://localhost' redirect URI -- use an app registration that "
        "does, or set GRAPH_ACCESS_TOKEN.",
        app.client_id,
    )
    return None


def _acquire_by_device_code(app: msal.PublicClientApplication) -> dict:
    """Sign in by entering a code at microsoft.com/devicelogin."""
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        msg = flow.get("error_description", "Failed to initiate device flow")
        raise GraphAuthError(msg)

    logger.warning(
        "\n  Visit: https://microsoft.com/devicelogin\n  Code:  %s\n",
        flow["user_code"],
    )
    webbrowser.open("https://microsoft.com/devicelogin")
    return app.acquire_token_by_device_flow(flow)


def get_token() -> str:
    """Acquire a Graph API access token.

    Tries each source in turn: an unexpired ``GRAPH_ACCESS_TOKEN``, a silent
    refresh from the on-disk cache, interactive browser sign-in (only when
    ``GRAPH_INTERACTIVE_AUTH`` opts in), then the device-code flow. Only the
    latter two prompt, and both cache a refresh token so subsequent calls
    renew silently.
    """
    supplied_token = _get_supplied_token()
    if supplied_token:
        return supplied_token

    app = _get_app()

    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            _save_cache(app)
            return result["access_token"]

    result = _acquire_interactive(app)
    if not result or "access_token" not in result:
        result = _acquire_by_device_code(app)

    if "access_token" in result:
        _save_cache(app)
        return result["access_token"]

    error = result.get("error_description", "Authentication failed")
    msg = (
        f"Authentication failed: {error}\n"
        "If Conditional Access blocks these flows, set GRAPH_ACCESS_TOKEN "
        "from https://developer.microsoft.com/graph/graph-explorer."
    )
    raise GraphAuthError(msg)


def _handle_response(resp: requests.Response) -> dict:
    """Raise on HTTP errors, return parsed JSON."""
    if resp.status_code == HTTPStatus.UNAUTHORIZED:
        msg = "Token expired or invalid. Re-run to authenticate."
        if _get_env("GRAPH_ACCESS_TOKEN"):
            msg = (
                "GRAPH_ACCESS_TOKEN was rejected. Confirm it grants Mail.Read "
                "(Mail.ReadWrite to modify), or unset it to sign in instead."
            )
        raise GraphAuthError(msg)
    resp.raise_for_status()
    return resp.json()


class GraphClient:
    """Read and manage Outlook emails via Microsoft Graph API."""

    def __init__(self, access_token: str | None = None) -> None:
        self._access_token = access_token

    def _headers(self) -> dict[str, str]:
        token = self._access_token or get_token()
        return {"Authorization": f"Bearer {token}"}

    def list_messages(
        self,
        *,
        folder: str = "inbox",
        limit: int = 25,
        unread_only: bool = False,
    ) -> list[dict]:
        """List recent messages, newest first."""
        url = f"{GRAPH_BASE}/mailFolders/{folder}/messages"
        params: dict[str, str | int] = {
            "$top": limit,
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,receivedDateTime,isRead",
        }
        if unread_only:
            params["$filter"] = "isRead eq false"

        resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
        data = _handle_response(resp)

        return [
            {
                "id": msg["id"],
                "subject": msg.get("subject", ""),
                "sender_name": msg.get("from", {})
                .get("emailAddress", {})
                .get("name", ""),
                "sender_address": msg.get("from", {})
                .get("emailAddress", {})
                .get("address", ""),
                "date": _parse_date(msg.get("receivedDateTime", "")),
                "is_read": msg.get("isRead", True),
            }
            for msg in data.get("value", [])
        ]

    def get_message(self, message_id: str) -> dict:
        """Get a single message with full body content."""
        url = f"{GRAPH_BASE}/messages/{message_id}"
        params = {"$select": "id,subject,from,receivedDateTime,isRead,body"}
        resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
        data = _handle_response(resp)

        return {
            "id": data["id"],
            "subject": data.get("subject", ""),
            "sender_name": data.get("from", {}).get("emailAddress", {}).get("name", ""),
            "sender_address": data.get("from", {})
            .get("emailAddress", {})
            .get("address", ""),
            "date": _parse_date(data.get("receivedDateTime", "")),
            "is_read": data.get("isRead", True),
            "body": data.get("body", {}).get("content", ""),
        }

    def mark_as_read(self, message_id: str) -> bool:
        """Mark a single message as read."""
        url = f"{GRAPH_BASE}/messages/{message_id}"
        resp = requests.patch(
            url,
            headers={**self._headers(), "Content-Type": "application/json"},
            data=json.dumps({"isRead": True}),
            timeout=30,
        )
        _handle_response(resp)
        return True

    def mark_all_as_read(self, *, folder: str = "inbox") -> int:
        """Mark all unread messages in a folder as read (paginates until empty)."""
        total_marked = 0
        while True:
            unread = self.list_messages(folder=folder, limit=100, unread_only=True)
            if not unread:
                return total_marked
            for msg in unread:
                self.mark_as_read(msg["id"])
            total_marked += len(unread)

    def delete_message(self, message_id: str) -> bool:
        """Delete a single message."""
        url = f"{GRAPH_BASE}/messages/{message_id}"
        resp = requests.delete(url, headers=self._headers(), timeout=30)
        if resp.status_code == HTTPStatus.NO_CONTENT:
            return True
        _handle_response(resp)
        return True
