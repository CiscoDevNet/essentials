"""Shared Playwright browser session with SSO handling."""

from .auth import (
    AUTH_DOMAINS,
    DUO_SKIP_UPDATE_SCRIPT,
    LOGIN_TIMEOUT_MS,
    is_auth_redirect,
    wait_for_login,
)
from .session import DEFAULT_PROFILE_DIR, BrowserSession

__all__ = [
    "AUTH_DOMAINS",
    "BrowserSession",
    "DEFAULT_PROFILE_DIR",
    "DUO_SKIP_UPDATE_SCRIPT",
    "LOGIN_TIMEOUT_MS",
    "is_auth_redirect",
    "wait_for_login",
]
