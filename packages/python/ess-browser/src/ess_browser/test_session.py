"""Unit tests for BrowserSession launch configuration."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest
from playwright.sync_api import Error as PlaywrightError

from .auth import DUO_SKIP_UPDATE_SCRIPT
from .session import BrowserSession, _safe_origin


class _TargetClosedError(PlaywrightError):
    """Mimics Playwright's private TargetClosedError for testing."""

    __name__ = "TargetClosedError"

    def __init__(
        self,
        message: str = "Target page, context or browser has been closed",
    ) -> None:
        super().__init__(message)


# Make type(exc).__name__ return "TargetClosedError" so _is_target_closed matches.
_TargetClosedError.__name__ = "TargetClosedError"


@pytest.fixture()
def _mock_playwright():
    """Patch sync_playwright so no real browser is launched."""
    with patch("ess_browser.session.sync_playwright") as factory:
        pw = MagicMock()
        factory.return_value.start.return_value = pw

        mock_page = MagicMock()
        mock_page.url = "about:blank"
        mock_page.is_closed.return_value = False
        mock_context = MagicMock()
        mock_context.pages = [mock_page]
        pw.chromium.launch_persistent_context.return_value = mock_context

        yield {
            "pw": pw,
            "context": mock_context,
            "page": mock_page,
        }


class TestEnableExtensions:
    """Verify ignore_default_args is set when extensions are enabled."""

    def test_extensions_enabled(self, _mock_playwright, tmp_path):
        session = BrowserSession(
            enable_extensions=True,
            profile_dir=tmp_path / "profile",
        )
        with session:
            kwargs = _mock_playwright["pw"].chromium.launch_persistent_context.call_args
            assert kwargs.kwargs.get("ignore_default_args") == ["--disable-extensions"]

    def test_extensions_disabled_by_default(self, _mock_playwright, tmp_path):
        session = BrowserSession(profile_dir=tmp_path / "profile")
        with session:
            kwargs = _mock_playwright["pw"].chromium.launch_persistent_context.call_args
            assert "ignore_default_args" not in kwargs.kwargs


class TestInitScripts:
    """Verify custom init scripts are injected."""

    def test_custom_init_scripts_added(self, _mock_playwright, tmp_path):
        custom = "console.log('hello');"
        session = BrowserSession(
            init_scripts=[custom],
            skip_duo_update_prompt=False,
            profile_dir=tmp_path / "profile",
        )
        with session:
            ctx = _mock_playwright["context"]
            ctx.add_init_script.assert_called_once_with(custom)

    def test_init_scripts_evaluated_on_existing_pages(self, _mock_playwright, tmp_path):
        custom = "console.log('hello');"
        _mock_playwright["page"].url = "https://example.com"
        session = BrowserSession(
            init_scripts=[custom],
            skip_duo_update_prompt=False,
            profile_dir=tmp_path / "profile",
        )
        with session:
            page = _mock_playwright["page"]
            page.evaluate.assert_called_once_with(custom)


class TestDuoSkipScript:
    """Verify DUO_SKIP_UPDATE_SCRIPT injection is controlled by the flag."""

    def test_duo_script_injected_by_default(self, _mock_playwright, tmp_path):
        session = BrowserSession(profile_dir=tmp_path / "profile")
        with session:
            ctx = _mock_playwright["context"]
            ctx.add_init_script.assert_any_call(DUO_SKIP_UPDATE_SCRIPT)

    def test_duo_script_skipped_when_disabled(self, _mock_playwright, tmp_path):
        session = BrowserSession(
            skip_duo_update_prompt=False,
            profile_dir=tmp_path / "profile",
        )
        with session:
            ctx = _mock_playwright["context"]
            ctx.add_init_script.assert_not_called()

    def test_duo_script_evaluated_on_existing_pages(self, _mock_playwright, tmp_path):
        _mock_playwright["page"].url = "https://example.com"
        session = BrowserSession(profile_dir=tmp_path / "profile")
        with session:
            page = _mock_playwright["page"]
            page.evaluate.assert_any_call(DUO_SKIP_UPDATE_SCRIPT)

    def test_duo_plus_custom_scripts_order(self, _mock_playwright, tmp_path):
        custom = "console.log('custom');"
        session = BrowserSession(
            init_scripts=[custom],
            profile_dir=tmp_path / "profile",
        )
        with session:
            ctx = _mock_playwright["context"]
            assert ctx.add_init_script.call_args_list == [
                call(DUO_SKIP_UPDATE_SCRIPT),
                call(custom),
            ]


class TestSafePageEvaluation:
    """Verify init scripts skip chrome:// and other unsafe pages."""

    def test_skips_chrome_urls(self, _mock_playwright, tmp_path):
        _mock_playwright["page"].url = "chrome://settings"
        session = BrowserSession(profile_dir=tmp_path / "profile")
        with session:
            _mock_playwright["page"].evaluate.assert_not_called()

    def test_skips_chrome_extension_urls(self, _mock_playwright, tmp_path):
        _mock_playwright["page"].url = "chrome-extension://abc/popup.html"
        session = BrowserSession(profile_dir=tmp_path / "profile")
        with session:
            _mock_playwright["page"].evaluate.assert_not_called()

    def test_skips_devtools_urls(self, _mock_playwright, tmp_path):
        _mock_playwright["page"].url = "devtools://devtools/bundled/inspector.html"
        session = BrowserSession(profile_dir=tmp_path / "profile")
        with session:
            _mock_playwright["page"].evaluate.assert_not_called()

    def test_skips_about_urls(self, _mock_playwright, tmp_path):
        _mock_playwright["page"].url = "about:blank"
        session = BrowserSession(profile_dir=tmp_path / "profile")
        with session:
            _mock_playwright["page"].evaluate.assert_not_called()

    def test_evaluate_failure_does_not_kill_session(self, _mock_playwright, tmp_path):
        _mock_playwright["page"].url = "https://example.com"
        _mock_playwright["page"].evaluate.side_effect = RuntimeError("CSP")
        session = BrowserSession(profile_dir=tmp_path / "profile")
        with session:
            assert session.context is not None

    def test_skips_closed_page(self, _mock_playwright, tmp_path):
        _mock_playwright["page"].is_closed.return_value = True
        session = BrowserSession(profile_dir=tmp_path / "profile")
        with session:
            _mock_playwright["page"].evaluate.assert_not_called()

    def test_handles_target_closed_on_url_access(self, _mock_playwright, tmp_path):
        page = _mock_playwright["page"]
        page.is_closed.return_value = False
        url_prop = PropertyMock(side_effect=_TargetClosedError())
        original = type(page).__dict__.get("url")
        type(page).url = url_prop
        try:
            session = BrowserSession(profile_dir=tmp_path / "profile")
            with session:
                page.evaluate.assert_not_called()
        finally:
            if original is None:
                del type(page).url
            else:
                type(page).url = original

    def test_target_closed_during_evaluate_does_not_kill_session(
        self, _mock_playwright, tmp_path
    ):
        _mock_playwright["page"].url = "https://example.com"
        _mock_playwright["page"].evaluate.side_effect = _TargetClosedError()
        session = BrowserSession(profile_dir=tmp_path / "profile")
        with session:
            assert session.context is not None

    def test_target_closed_with_custom_message(self, _mock_playwright, tmp_path):
        _mock_playwright["page"].url = "https://example.com"
        _mock_playwright["page"].evaluate.side_effect = _TargetClosedError(
            "Connection closed",
        )
        session = BrowserSession(profile_dir=tmp_path / "profile")
        with session:
            assert session.context is not None

    def test_plain_error_with_target_closed_message(self, _mock_playwright, tmp_path):
        _mock_playwright["page"].url = "https://example.com"
        _mock_playwright["page"].evaluate.side_effect = PlaywrightError(
            "Target page, context or browser has been closed",
        )
        session = BrowserSession(profile_dir=tmp_path / "profile")
        with session:
            assert session.context is not None

    def test_plain_error_with_target_closed_message_on_url(
        self, _mock_playwright, tmp_path
    ):
        page = _mock_playwright["page"]
        page.is_closed.return_value = False
        url_prop = PropertyMock(
            side_effect=PlaywrightError(
                "Target page, context or browser has been closed",
            ),
        )
        original = type(page).__dict__.get("url")
        type(page).url = url_prop
        try:
            session = BrowserSession(profile_dir=tmp_path / "profile")
            with session:
                page.evaluate.assert_not_called()
        finally:
            if original is None:
                del type(page).url
            else:
                type(page).url = original

    def test_short_target_closed_is_not_suppressed(self, _mock_playwright, tmp_path):
        _mock_playwright["page"].url = "https://example.com"
        _mock_playwright["page"].evaluate.side_effect = PlaywrightError(
            "Target closed",
        )
        session = BrowserSession(profile_dir=tmp_path / "profile")
        with session:
            assert session.context is not None
            _mock_playwright["page"].evaluate.assert_called()

    def test_browser_closed_is_not_suppressed(self, _mock_playwright, tmp_path):
        _mock_playwright["page"].url = "https://example.com"
        _mock_playwright["page"].evaluate.side_effect = PlaywrightError(
            "Browser has been closed",
        )
        session = BrowserSession(profile_dir=tmp_path / "profile")
        with session:
            assert session.context is not None
            _mock_playwright["page"].evaluate.assert_called()

    def test_non_target_playwright_error_from_url_is_raised(
        self, _mock_playwright, tmp_path
    ):
        page = _mock_playwright["page"]
        page.is_closed.return_value = False
        url_prop = PropertyMock(
            side_effect=PlaywrightError("Protocol error"),
        )
        original = type(page).__dict__.get("url")
        type(page).url = url_prop
        try:
            session = BrowserSession(profile_dir=tmp_path / "profile")
            with pytest.raises(PlaywrightError, match="Protocol error"):
                session.__enter__()
        finally:
            if original is None:
                del type(page).url
            else:
                type(page).url = original


class TestSafeOrigin:
    """Verify _safe_origin strips secrets and sensitive paths."""

    def test_strips_query_and_path(self):
        assert _safe_origin("https://example.com/path?token=secret") == (
            "https://example.com"
        )

    def test_strips_userinfo(self):
        assert _safe_origin("https://alice:x@host.com/p") == ("https://host.com")

    def test_preserves_port(self):
        assert _safe_origin("https://host.com:8443/p") == ("https://host.com:8443")

    def test_file_url_returns_scheme_only(self):
        assert _safe_origin("file:///etc/passwd") == "file:"

    def test_data_url_returns_scheme_only(self):
        assert _safe_origin("data:text/html,<h1>hi</h1>") == "data:"

    def test_malformed_port_does_not_raise(self):
        assert _safe_origin("https://host:bad/path") == "https://host"

    def test_ipv6_brackets_preserved(self):
        assert _safe_origin("https://[::1]:8443/path") == "https://[::1]:8443"

    def test_ipv6_no_port(self):
        assert _safe_origin("https://[::1]/path") == "https://[::1]"

    def test_scheme_relative_url(self):
        assert _safe_origin("//example.com/path") == "//example.com"

    def test_scheme_relative_url_with_port(self):
        assert _safe_origin("//example.com:9090/path") == "//example.com:9090"

    def test_empty_string(self):
        assert _safe_origin("") == "<unknown>"
