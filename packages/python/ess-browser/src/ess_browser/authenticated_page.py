"""Authenticated page sessions for SSO-protected sites."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .auth import LOGIN_TIMEOUT_MS, is_auth_redirect, wait_for_login
from .exceptions import SsoTimeoutError, sso_timeout_message
from .session import BrowserSession
from .site import SsoSite

logger = logging.getLogger(__name__)


@contextmanager
def open_authenticated_page(
    site: SsoSite,
    *,
    headed: bool,
    profile_dir: Path | str | None = None,
    prepare: Callable[[Page], None] | None = None,
) -> Iterator[Page]:
    """Open *site* in a browser tab that has completed SSO.

    Reuses the saved session in *profile_dir* when it is still valid.
    When it is not, and the window is visible, this blocks until the
    user finishes logging in.

    Args:
        site: The site to open, including its SSO quirks.
        headed: Show the browser window.
        profile_dir: Browser profile directory for session persistence.
        prepare: Called with the blank page before the first navigation.
            Use it to attach listeners that would otherwise miss the
            traffic that navigation itself generates.

    Yields:
        A Playwright page sitting on an authenticated URL of *site*.

    Raises:
        SsoTimeoutError: Login did not complete within the timeout.
    """
    with BrowserSession(headed=headed, profile_dir=profile_dir) as browser:
        page = browser.new_page()
        if prepare is not None:
            prepare(page)
        logger.info("Navigating to %s", site.url)
        page.goto(site.url, wait_until="load", timeout=site.nav_timeout_ms)
        if site.settle_ms:
            page.wait_for_timeout(site.settle_ms)
        _complete_login(page, site, headed=headed)
        yield page


def _complete_login(page: Page, site: SsoSite, *, headed: bool) -> None:
    """Wait out an SSO redirect, then return to the requested page."""
    if not is_auth_redirect(
        page.url,
        site.url,
        extra_auth_domains=site.extra_auth_domains,
    ):
        return

    logger.info("SSO redirect detected -- waiting for login")
    try:
        wait_for_login(page, site.login_target, timeout_ms=LOGIN_TIMEOUT_MS)
    except PlaywrightTimeoutError as exc:
        raise SsoTimeoutError(sso_timeout_message(headed=headed)) from exc

    # Login ends on the IdP callback landing page, which is not
    # necessarily the page that was asked for.
    if not page.url.startswith(site.url):
        logger.info("Returning to %s after login", site.url)
        page.goto(site.url, wait_until="load", timeout=site.nav_timeout_ms)
