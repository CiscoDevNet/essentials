"""SSO redirect detection and login-wait helpers."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Page

logger = logging.getLogger(__name__)

LOGIN_TIMEOUT_MS = 5 * 60 * 1000  # 5 minutes
SSO_SETTLE_MS = 5_000
NAV_TIMEOUT_MS = 60_000

# Public IdPs only. Callers pass a company's own login hosts as
# ``extra_auth_domains``.
AUTH_DOMAINS: tuple[str, ...] = (
    # Duo
    "duosecurity.com",
    "login.duosecurity.com",
    "sso.duosecurity.com",
    "duomobile.com",
    # Microsoft
    "login.microsoftonline.com",
    "login.live.com",
    # Google
    "accounts.google.com",
    # Other IdPs
    "auth0.com",
    "okta.com",
    # Generic patterns (substring match)
    "sso.",
    "idp.",
    "adfs.",
)


# JS init script that auto-dismisses the Duo "update Chrome" prompt.
# Only runs on ``duosecurity.com`` and its subdomains; exits immediately
# on all other pages.
DUO_SKIP_UPDATE_SCRIPT = """\
(() => {
  "use strict";
  const hostname = location.hostname;
  // Init script runs on every navigation; no-op outside Duo-hosted pages.
  if (hostname !== "duosecurity.com" && !hostname.endsWith(".duosecurity.com")) return;

  const SKIP_TEXT = "Skip for now";
  const CLICK_DELAY_MS = 500;
  const OBSERVER_TIMEOUT_MS = 15000;

  function findSkipButton() {
    const buttons = document.querySelectorAll(
      "#pwl-prompt-root button.button--link"
    );
    for (const button of buttons) {
      if (button.textContent.trim() === SKIP_TEXT) {
        return button;
      }
    }
    return null;
  }

  function clickAfterDelay(button) {
    setTimeout(() => {
      button.click();
      console.log("[duo-skip-chrome-update] Clicked '%s'", SKIP_TEXT);
    }, CLICK_DELAY_MS);
  }

  function tryClick() {
    const button = findSkipButton();
    if (button) {
      clickAfterDelay(button);
      return true;
    }
    return false;
  }

  if (!tryClick()) {
    const root = document.body || document.documentElement;
    const observer = new MutationObserver(() => {
      if (tryClick()) {
        observer.disconnect();
      }
    });

    observer.observe(root, { childList: true, subtree: true });

    setTimeout(() => {
      observer.disconnect();
      console.log(
        "[duo-skip-chrome-update] Timed out waiting for '%s' button",
        SKIP_TEXT
      );
    }, OBSERVER_TIMEOUT_MS);
  }
})();
"""


def is_auth_redirect(
    current_url: str,
    target_url: str,
    *,
    extra_auth_domains: tuple[str, ...] = (),
) -> bool:
    """Return True if the browser landed on an SSO page instead of the target.

    Args:
        current_url: Where the browser actually is.
        target_url: Where it was asked to go.
        extra_auth_domains: Host patterns to recognize as IdPs in
            addition to :data:`AUTH_DOMAINS`. Lets one caller teach this
            check about a tenant-specific IdP without widening the
            shared tuple for everybody.
    """
    current_host = urlparse(current_url).netloc.lower()
    target_host = urlparse(target_url).netloc.lower()
    if current_host == target_host:
        return False
    domains = AUTH_DOMAINS + extra_auth_domains
    return any(domain in current_host for domain in domains)


def _is_profile_empty(profile_dir: Path) -> bool:
    if not profile_dir.is_dir():
        return True
    return not any(profile_dir.iterdir())


def is_sso_login_required(
    target_url: str,
    *,
    profile_dir: Path | str,
    settle_timeout_ms: int = SSO_SETTLE_MS,
    extra_auth_domains: tuple[str, ...] = (),
) -> bool:
    """Return True when a headless visit to ``target_url`` lands on SSO.

    Best-effort probe: navigation or browser errors are logged and treated as
    ``False`` so callers can attempt headless execution and apply their own
    SSO retry logic.

    Args:
        target_url: The page to probe.
        profile_dir: Browser profile directory holding the saved session.
        settle_timeout_ms: Grace period before reading the landed URL.
        extra_auth_domains: Additional IdP host patterns, passed through
            to :func:`is_auth_redirect` so the probe agrees with the
            real run.
    """
    from ess_browser.session import BrowserSession  # noqa: PLC0415, I001 — session imports auth; lazy import breaks cycle

    effective_profile = Path(profile_dir)

    try:
        # No persisted cookies yet — skip the probe and require headed login once.
        if _is_profile_empty(effective_profile):
            return True

        with BrowserSession(headed=False, profile_dir=effective_profile) as session:
            page = session.new_page()
            page.goto(target_url, wait_until="load", timeout=NAV_TIMEOUT_MS)
            page.wait_for_timeout(settle_timeout_ms)
            return is_auth_redirect(
                page.url,
                target_url,
                extra_auth_domains=extra_auth_domains,
            )
    except Exception as exc:
        logger.warning(
            "SSO probe failed for %s (profile %s): %s — assuming session is valid",
            target_url,
            effective_profile,
            exc,
        )
        return False


def wait_for_login(
    page: Page,
    target_url: str,
    timeout_ms: int = LOGIN_TIMEOUT_MS,
) -> None:
    """Block until the user completes SSO and the browser returns to the target.

    Args:
        page: The Playwright page currently on an SSO login screen.
        target_url: The URL the browser should return to after login.
        timeout_ms: Maximum time to wait for login completion.
    """
    target_host = urlparse(target_url).netloc.lower()
    msg = (
        "SSO login required — please authenticate in the browser window. "
        f"Waiting up to {timeout_ms // 1000} seconds ..."
    )
    print(msg, file=sys.stderr)
    logger.warning(msg)
    page.wait_for_url(
        f"**://{target_host}/**",
        timeout=timeout_ms,
        wait_until="load",
    )
    print("SSO login complete.", file=sys.stderr)
    logger.info("SSO login complete.")
