"""Per-site SSO facts and headed-mode selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .auth import NAV_TIMEOUT_MS, SSO_SETTLE_MS, is_sso_login_required


@dataclass(frozen=True)
class SsoSite:
    """The auth-relevant facts about one SSO-protected site.

    Declare one per site as a module constant and hand it to
    :func:`ess_browser.open_authenticated_page`. Collecting the facts in
    one object is what keeps each consumer from threading the same
    handful of keyword arguments through its own session helper.

    Attributes:
        url: The page to open. Its host is also what "authenticated"
            means for this site.
        login_complete_url: Where the IdP lands after a successful login,
            when that is not ``url``. An OIDC callback may always return
            to one canonical host regardless of which URL began the flow,
            in which case waiting on ``url`` would wait forever.
        settle_ms: Grace period after load before judging whether this is
            an SSO redirect. Needed for sites that redirect from
            client-side JavaScript rather than an HTTP response, where
            the first load lands on the app briefly before bouncing.
        nav_timeout_ms: Navigation timeout for this site.
        extra_auth_domains: IdP host patterns to recognize in addition to
            :data:`ess_browser.AUTH_DOMAINS`. Name a tenant's own IdP
            here rather than widening the shared tuple.
    """

    url: str
    login_complete_url: str | None = None
    settle_ms: int = 0
    nav_timeout_ms: int = NAV_TIMEOUT_MS
    extra_auth_domains: tuple[str, ...] = ()

    @property
    def login_target(self) -> str:
        """The URL that signals login is complete."""
        return self.login_complete_url or self.url


def should_use_headed_browser(
    site: SsoSite,
    *,
    profile_dir: Path | str,
    force_headed: bool = False,
    force_headless: bool = False,
) -> bool:
    """Decide whether the browser window needs to be visible.

    Args:
        site: The site whose saved session is probed.
        profile_dir: Browser profile directory holding that session.
        force_headed: Always show the window.
        force_headless: Never show the window.

    Returns:
        True when a visible window is needed, either because it was
        forced or because the saved SSO session has expired.

    Raises:
        ValueError: Both force flags were set.
    """
    if force_headed and force_headless:
        msg = "Cannot pass both --headed and --headless"
        raise ValueError(msg)
    if force_headed:
        return True
    if force_headless:
        return False
    return is_sso_login_required(
        site.url,
        profile_dir=profile_dir,
        settle_timeout_ms=site.settle_ms or SSO_SETTLE_MS,
        extra_auth_domains=site.extra_auth_domains,
    )
