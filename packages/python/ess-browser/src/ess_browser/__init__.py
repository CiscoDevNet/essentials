"""Shared Playwright browser session with SSO handling."""

from .auth import (
    AUTH_DOMAINS,
    DUO_SKIP_UPDATE_SCRIPT,
    LOGIN_TIMEOUT_MS,
    NAV_TIMEOUT_MS,
    SSO_SETTLE_MS,
    is_auth_redirect,
    is_sso_login_required,
    wait_for_login,
)
from .authenticated_page import open_authenticated_page
from .exceptions import EssBrowserError, SsoTimeoutError, sso_timeout_message
from .session import (
    DEFAULT_PROFILE_DIR,
    BrowserSession,
    default_profile_dir,
    profile_dir_display,
)
from .site import SsoSite, should_use_headed_browser

__all__ = [
    "AUTH_DOMAINS",
    "BrowserSession",
    "DEFAULT_PROFILE_DIR",
    "DUO_SKIP_UPDATE_SCRIPT",
    "EssBrowserError",
    "LOGIN_TIMEOUT_MS",
    "NAV_TIMEOUT_MS",
    "SSO_SETTLE_MS",
    "SsoSite",
    "SsoTimeoutError",
    "default_profile_dir",
    "is_auth_redirect",
    "is_sso_login_required",
    "open_authenticated_page",
    "profile_dir_display",
    "should_use_headed_browser",
    "sso_timeout_message",
    "wait_for_login",
]
