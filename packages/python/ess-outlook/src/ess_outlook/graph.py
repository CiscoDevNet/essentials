"""Microsoft Graph API client for Outlook email."""

from __future__ import annotations

import json
import logging
import os
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus

import msal
import requests
from ess_dirs import write_secure

GRAPH_BASE = "https://graph.microsoft.com/v1.0/me"
TOKEN_CACHE = os.path.expanduser("~/.cache/ess-outlook/graph_token_cache.json")
SCOPES = ["Mail.ReadWrite"]

logger = logging.getLogger(__name__)


class GraphAuthError(Exception):
    """Raised when Graph API authentication fails."""


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
    client_id = os.environ.get("CLIENT_ID")
    tenant_id = os.environ.get("TENANT_ID")
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


def get_token() -> str:
    """Acquire a Graph API access token (silent refresh or device-code flow)."""
    app = _get_app()

    # 1. Try silent refresh from cached account
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            _save_cache(app)
            return result["access_token"]

    # 2. Device-code flow -- open browser automatically
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        msg = flow.get("error_description", "Failed to initiate device flow")
        raise GraphAuthError(msg)

    code = flow["user_code"]
    logger.warning(
        "\n  Visit: https://microsoft.com/devicelogin\n  Code:  %s\n",
        code,
    )
    webbrowser.open("https://microsoft.com/devicelogin")
    result = app.acquire_token_by_device_flow(flow)

    if "access_token" in result:
        _save_cache(app)
        return result["access_token"]

    # 3. Auth failed -- give actionable error
    error = result.get("error_description", "Authentication failed")
    msg = (
        f"Authentication failed: {error}\n"
        "If blocked by Conditional Access, try from your terminal."
    )
    raise GraphAuthError(msg)


def _handle_response(resp: requests.Response) -> dict:
    """Raise on HTTP errors, return parsed JSON."""
    if resp.status_code == HTTPStatus.UNAUTHORIZED:
        msg = "Token expired or invalid. Re-run to authenticate."
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
