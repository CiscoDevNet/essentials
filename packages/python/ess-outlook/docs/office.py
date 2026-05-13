#!/usr/bin/env python3
"""
Microsoft Graph API auth for a Microsoft Entra (Azure AD) tenant.
Uses the Office Desktop Apps client ID, which is pre-approved on most
Microsoft 365 tenants.

Usage:
python3 office.py          # Get token (silent refresh or device code)
python3 office.py --check  # Check if current token is valid, refresh if not

Token saved to ~/.cache/ess-outlook/graph_token.txt
Refresh token cached to ~/.cache/ess-outlook/graph_token_cache.json
(~90 day TTL, renews on use)
Access token TTL: ~75 minutes (auto-refreshes via cache)
"""

import base64
import json
import os
import sys
import time
import webbrowser

import msal
from dotenv import load_dotenv
from ess_dirs import write_secure

load_dotenv()

CLIENT_ID = os.environ["CLIENT_ID"]  # Office Desktop Apps client ID
TENANT_ID = os.environ["TENANT_ID"]  # Your organization's Entra tenant ID
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]
TOKEN_CACHE = os.path.expanduser("~/.cache/ess-outlook/graph_token_cache.json")
TOKEN_FILE = os.path.expanduser("~/.cache/ess-outlook/graph_token.txt")


def _token_expired():
    """Check if the saved access token is expired or about to expire (5 min buffer)."""
    if not os.path.exists(TOKEN_FILE):
        return True
    try:
        with open(TOKEN_FILE) as f:
            token = f.read().strip()
        payload = token.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return time.time() > (claims.get("exp", 0) - 300)
    except Exception:
        return True


def _save(cache, token):
    write_secure(TOKEN_CACHE, cache.serialize())
    write_secure(TOKEN_FILE, token)
    print(token)


def get_token(force=False):
    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE):
        with open(TOKEN_CACHE, "r") as f:
            cache.deserialize(f.read())

    app = msal.PublicClientApplication(
        CLIENT_ID, authority=AUTHORITY, token_cache=cache
    )

    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            _save(cache, result["access_token"])
            print(f"Refreshed token for {accounts[0]['username']}", file=sys.stderr)
            return result["access_token"]

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        print(f"Error: {flow.get('error_description', 'unknown')}", file=sys.stderr)
        sys.exit(1)

    code = flow["user_code"]
    print(f"Opening browser... Enter code: {code}", file=sys.stderr)
    webbrowser.open("https://login.microsoft.com/device")
    result = app.acquire_token_by_device_flow(flow)

    if "access_token" in result:
        _save(cache, result["access_token"])
        user = result.get("id_token_claims", {}).get("preferred_username", "unknown")
        print(f"Authenticated as {user}", file=sys.stderr)
        return result["access_token"]
    else:
        print(f"Error: {result.get('error_description', 'unknown')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if "--check" in sys.argv:
        if _token_expired():
            print("Token expired or missing, refreshing...", file=sys.stderr)
            get_token()
        else:
            print("Token valid", file=sys.stderr)
            with open(TOKEN_FILE) as f:
                print(f.read().strip())
    else:
        get_token()
