"""SSO redirect detection and login-wait helpers."""

from __future__ import annotations

import logging
import sys
from urllib.parse import urlparse

from playwright.sync_api import Page

logger = logging.getLogger(__name__)

LOGIN_TIMEOUT_MS = 5 * 60 * 1000  # 5 minutes

AUTH_DOMAINS: tuple[str, ...] = (
    # Cisco
    "id.cisco.com",
    "cloudsso.cisco.com",
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


def is_auth_redirect(current_url: str, target_url: str) -> bool:
    """Return True if the browser landed on an SSO page instead of the target."""
    current_host = urlparse(current_url).netloc.lower()
    target_host = urlparse(target_url).netloc.lower()
    if current_host == target_host:
        return False
    return any(domain in current_host for domain in AUTH_DOMAINS)


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
