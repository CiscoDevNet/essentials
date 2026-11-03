"""Browser-based SSO auth via system Chrome (ess-browser)."""

import logging
import time
from pathlib import Path
from urllib.parse import urlparse

from ess_browser import LOGIN_TIMEOUT_MS, BrowserSession
from playwright.sync_api import Page, Request

logger = logging.getLogger(__name__)

_NEXT_AUTH_COOKIE_NAMES = frozenset(
    {
        "next-auth.session-token",
        "__Secure-next-auth.session-token",
        "__Host-next-auth.session-token",
    }
)


class BrowserAuthError(ValueError):
    """Raised when browser SSO auth cannot produce a load-test header."""


def _normalize_host(hostname: str) -> str:
    return hostname.lower().removeprefix("www.")


def _host_matches(request_host: str, target_host: str) -> bool:
    normalized_request = _normalize_host(request_host)
    normalized_target = _normalize_host(target_host)
    return normalized_request == normalized_target or normalized_request.endswith(
        f".{normalized_target}"
    )


def _authorization_from_request(request: Request, target_host: str) -> str | None:
    auth_value = request.headers.get("authorization")
    if not auth_value:
        return None
    request_host = urlparse(request.url).hostname
    if not request_host or not _host_matches(request_host, target_host):
        return None
    if auth_value.lower().startswith("bearer "):
        return f"Authorization: {auth_value}"
    return f"Authorization: Bearer {auth_value}"


def _cookies_to_header(page: Page, target_url: str) -> str | None:
    cookies = page.context.cookies([target_url])
    if not cookies:
        return None
    cookie_pairs = [f"{cookie['name']}={cookie['value']}" for cookie in cookies]
    return f"Cookie: {'; '.join(cookie_pairs)}"


def _has_auth_session(page: Page, target_url: str) -> bool:
    """Return True when NextAuth session cookies are present for the target."""
    cookies = page.context.cookies([target_url])
    return any(cookie["name"] in _NEXT_AUTH_COOKIE_NAMES for cookie in cookies)


def _has_any_cookies(page: Page, target_url: str) -> bool:
    return bool(page.context.cookies([target_url]))


def _wait_for_target_session(
    page: Page,
    target_url: str,
    *,
    headed: bool,
    captured_headers: list[str],
    extra_auth_domains: tuple[str, ...] = (),
) -> None:
    """Navigate to the target and wait until SSO produces a usable session."""
    page.goto(target_url, wait_until="load", timeout=LOGIN_TIMEOUT_MS)
    deadline = time.time() + LOGIN_TIMEOUT_MS / 1000

    if headed:
        logger.info(
            "Complete SSO in the Chrome window. The browser closes automatically "
            "once login is detected."
        )

    while time.time() < deadline:
        if captured_headers:
            return
        if BrowserSession.is_auth_redirect(
            page.url,
            target_url,
            extra_auth_domains=extra_auth_domains,
        ):
            if not headed:
                msg = (
                    "SSO login is required but the browser is headless. "
                    "Re-run with --headed to complete login in system Chrome."
                )
                raise BrowserAuthError(msg)
            remaining_ms = max(1000, int((deadline - time.time()) * 1000))
            BrowserSession.wait_for_login(
                page,
                target_url,
                timeout_ms=remaining_ms,
            )
        elif _has_auth_session(page, target_url):
            return
        elif not headed and _has_any_cookies(page, target_url):
            return
        time.sleep(0.5)

    msg = (
        "Timed out waiting for browser SSO login. "
        "Re-run with --headed and complete SSO in Chrome."
    )
    raise BrowserAuthError(msg)


def establish_browser_session(
    target_url: str,
    *,
    profile_dir: Path,
    headed: bool = True,
    extra_auth_domains: tuple[str, ...] = (),
) -> None:
    """Open system Chrome and wait until SSO session cookies are saved.

    ``extra_auth_domains`` names IdP hosts beyond ess-browser's public
    ``AUTH_DOMAINS``, such as your organization's own login host.
    """
    if not target_url.strip():
        msg = "Target URL is required for browser login."
        raise BrowserAuthError(msg)

    captured_headers: list[str] = []

    with BrowserSession(headed=headed, profile_dir=profile_dir) as session:
        page = session.new_page()
        _wait_for_target_session(
            page,
            target_url,
            headed=headed,
            captured_headers=captured_headers,
            extra_auth_domains=extra_auth_domains,
        )

    logger.info("Browser session saved in %s", profile_dir)


def fetch_auth_header_via_browser(
    target_url: str,
    *,
    profile_dir: Path,
    headed: bool = True,
    extra_auth_domains: tuple[str, ...] = (),
) -> str:
    """Log in via system Chrome and return a Locust auth header value.

    ``extra_auth_domains`` names IdP hosts beyond ess-browser's public
    ``AUTH_DOMAINS``, such as your organization's own login host.
    """
    if not target_url.strip():
        msg = "Target URL is required for browser auth."
        raise BrowserAuthError(msg)

    target_host = urlparse(target_url).hostname
    if not target_host:
        msg = f"Invalid target URL for browser auth: {target_url!r}"
        raise BrowserAuthError(msg)

    captured_headers: list[str] = []

    def on_request(request: Request) -> None:
        header = _authorization_from_request(request, target_host)
        if header:
            captured_headers.append(header)

    with BrowserSession(headed=headed, profile_dir=profile_dir) as session:
        page = session.new_page()
        page.on("request", on_request)
        _wait_for_target_session(
            page,
            target_url,
            headed=headed,
            captured_headers=captured_headers,
            extra_auth_domains=extra_auth_domains,
        )

        if captured_headers:
            return captured_headers[-1]

        cookie_header = _cookies_to_header(page, target_url)
        if cookie_header:
            return cookie_header

    msg = (
        "Browser login completed but no Authorization header or session cookies "
        f"were found for {target_url}. Try `browser login --headed` first, "
        "or set LOAD_TEST_AUTH_HEADER manually."
    )
    raise BrowserAuthError(msg)
