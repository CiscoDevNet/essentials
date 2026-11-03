"""Unit tests for the authenticated page context manager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .authenticated_page import open_authenticated_page
from .exceptions import SsoTimeoutError, sso_timeout_message
from .site import SsoSite

APP_URL = "https://app.example.com/"
IDP_URL = "https://sso.example.com/login"

# Deliberately matches no AUTH_DOMAINS entry -- note that the generic
# "idp." pattern would swallow any host containing it, which would make
# the extra_auth_domains tests below pass for the wrong reason.
TENANT_IDP_URL = "https://auth.tenant.example.com/authorize"

# One navigation to arrive, then a second to return to the requested page
# after the IdP callback dropped the browser somewhere else.
NAVIGATIONS_WITH_RETURN_TRIP = 2


@pytest.fixture
def page() -> MagicMock:
    mock_page = MagicMock()
    mock_page.url = APP_URL
    return mock_page


@pytest.fixture
def session(page: MagicMock):
    """Patch BrowserSession so no real Chrome is launched."""
    with patch("ess_browser.authenticated_page.BrowserSession") as session_cls:
        session_cls.return_value.__enter__.return_value.new_page.return_value = page
        yield session_cls


class TestHappyPath:
    def test_yields_the_page_without_waiting_when_already_signed_in(
        self, session: MagicMock, page: MagicMock
    ) -> None:
        site = SsoSite(url=APP_URL)

        with patch("ess_browser.authenticated_page.wait_for_login") as wait:
            with open_authenticated_page(site, headed=False) as yielded:
                assert yielded is page

        wait.assert_not_called()
        page.goto.assert_called_once_with(
            APP_URL, wait_until="load", timeout=site.nav_timeout_ms
        )

    def test_prepare_runs_before_the_first_navigation(
        self, session: MagicMock, page: MagicMock
    ) -> None:
        """Listeners attached after goto would miss the navigation traffic."""
        calls: list[str] = []
        page.goto.side_effect = lambda *a, **k: calls.append("goto")

        with open_authenticated_page(
            SsoSite(url=APP_URL),
            headed=False,
            prepare=lambda _page: calls.append("prepare"),
        ):
            pass

        assert calls == ["prepare", "goto"]

    def test_settle_wait_only_happens_when_configured(
        self, session: MagicMock, page: MagicMock
    ) -> None:
        with open_authenticated_page(SsoSite(url=APP_URL), headed=False):
            pass
        page.wait_for_timeout.assert_not_called()

        with open_authenticated_page(
            SsoSite(url=APP_URL, settle_ms=1_500), headed=False
        ):
            pass
        page.wait_for_timeout.assert_called_once_with(1_500)


class TestSsoRedirect:
    def test_waits_for_login_then_returns_to_the_target(
        self, session: MagicMock, page: MagicMock
    ) -> None:
        page.url = IDP_URL
        site = SsoSite(url=APP_URL)

        with patch("ess_browser.authenticated_page.wait_for_login") as wait:
            with open_authenticated_page(site, headed=True):
                pass

        wait.assert_called_once()
        assert wait.call_args[0][1] == APP_URL
        # Still on the IdP host after login, so a second goto is required.
        assert page.goto.call_count == NAVIGATIONS_WITH_RETURN_TRIP

    def test_waits_on_the_callback_host_not_the_target(
        self, session: MagicMock, page: MagicMock
    ) -> None:
        """A callback that always lands elsewhere would otherwise hang."""
        page.url = IDP_URL
        site = SsoSite(
            url="https://alias.example.com/goals",
            login_complete_url=APP_URL,
        )

        with patch("ess_browser.authenticated_page.wait_for_login") as wait:
            with open_authenticated_page(site, headed=True):
                pass

        assert wait.call_args[0][1] == APP_URL

    def test_no_second_navigation_when_login_lands_on_target(
        self, session: MagicMock, page: MagicMock
    ) -> None:
        page.url = IDP_URL
        site = SsoSite(url=APP_URL)

        def land_on_target(*_args: object, **_kwargs: object) -> None:
            page.url = f"{APP_URL}dashboard"

        with patch(
            "ess_browser.authenticated_page.wait_for_login",
            side_effect=land_on_target,
        ):
            with open_authenticated_page(site, headed=True):
                pass

        assert page.goto.call_count == 1

    def test_extra_auth_domains_are_honored(
        self, session: MagicMock, page: MagicMock
    ) -> None:
        """A tenant IdP unknown to AUTH_DOMAINS must still be detected."""
        page.url = TENANT_IDP_URL
        site = SsoSite(url=APP_URL, extra_auth_domains=("tenant.example.com",))

        with patch("ess_browser.authenticated_page.wait_for_login") as wait:
            with open_authenticated_page(site, headed=True):
                pass

        wait.assert_called_once()

    def test_unknown_idp_host_is_not_detected_without_extras(
        self, session: MagicMock, page: MagicMock
    ) -> None:
        """Guards the test above: without extras this host is invisible."""
        page.url = TENANT_IDP_URL

        with patch("ess_browser.authenticated_page.wait_for_login") as wait:
            with open_authenticated_page(SsoSite(url=APP_URL), headed=True):
                pass

        wait.assert_not_called()


class TestTimeout:
    def test_playwright_timeout_becomes_sso_timeout_error(
        self, session: MagicMock, page: MagicMock
    ) -> None:
        page.url = IDP_URL

        with patch(
            "ess_browser.authenticated_page.wait_for_login",
            side_effect=PlaywrightTimeoutError("Timeout 300000ms exceeded"),
        ):
            with pytest.raises(SsoTimeoutError) as excinfo:
                with open_authenticated_page(SsoSite(url=APP_URL), headed=False):
                    pass

        assert "--headed" in str(excinfo.value)

    def test_headed_timeout_omits_the_retry_hint(
        self, session: MagicMock, page: MagicMock
    ) -> None:
        page.url = IDP_URL

        with patch(
            "ess_browser.authenticated_page.wait_for_login",
            side_effect=PlaywrightTimeoutError("Timeout 300000ms exceeded"),
        ):
            with pytest.raises(SsoTimeoutError) as excinfo:
                with open_authenticated_page(SsoSite(url=APP_URL), headed=True):
                    pass

        assert "--headed" not in str(excinfo.value)


class TestSsoTimeoutMessage:
    def test_headless_gets_an_actionable_hint(self) -> None:
        assert "--headed" in sso_timeout_message(headed=False)

    def test_a_caller_can_name_its_own_option(self) -> None:
        """Not every CLI spells this `--headed`; sending them there misleads."""
        message = sso_timeout_message(
            headed=False,
            retry_hint=" Re-run with --browser headed.",
        )
        assert "--browser headed" in message
        assert "--headed to complete" not in message

    def test_headed_gets_no_hint(self) -> None:
        assert sso_timeout_message(headed=True) == "SSO authentication timed out."

    def test_prefix_is_overridable(self) -> None:
        message = sso_timeout_message(headed=True, prefix="Tenant SSO timed out")

        assert message == "Tenant SSO timed out."
