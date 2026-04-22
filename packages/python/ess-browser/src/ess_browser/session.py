"""Persistent Chrome browser session with SSO support."""

from __future__ import annotations

import logging
from pathlib import Path
from types import TracebackType
from urllib.parse import urlparse

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright
from playwright.sync_api import Error as PlaywrightError

from .auth import DUO_SKIP_UPDATE_SCRIPT, is_auth_redirect, wait_for_login

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_DIR = Path.home() / ".ess-browser" / "profile"
_DEFAULT_VIEWPORT = {"width": 1280, "height": 900}
_UNSAFE_URL_PREFIXES = ("chrome://", "chrome-extension://", "about:", "devtools://")


_TARGET_CLOSED_MESSAGE = "Target page, context or browser has been closed"


def _is_target_closed(exc: PlaywrightError) -> bool:
    """True when *exc* signals a closed page/context/browser.

    Playwright may raise either the private ``TargetClosedError``
    subclass or a plain ``Error`` with the canonical message, depending
    on the code path and library version.  We check the class name
    first, then fall back to a substring match on the canonical message.
    """
    if type(exc).__name__ == "TargetClosedError":
        return True
    return _TARGET_CLOSED_MESSAGE in str(exc)


def _safe_origin(url: str) -> str:
    """Return the origin for logging without leaking secrets.

    Strips query params, fragments, paths, and ``user:pass@`` from the
    URL.  Returns ``scheme://host[:port]`` for network URLs,
    ``//host[:port]`` for scheme-relative URLs, or just ``scheme:``
    for URLs without a network host (``file:``, ``data:``, etc.).
    """
    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return "<unknown>"
    if not parsed.hostname:
        return f"{parsed.scheme}:" if parsed.scheme else "<unknown>"

    hostname = parsed.hostname
    if ":" in hostname:
        hostname = f"[{hostname}]"

    try:
        port = f":{parsed.port}" if parsed.port else ""
    except ValueError:
        port = ""

    if not parsed.scheme:
        return f"//{hostname}{port}"
    return f"{parsed.scheme}://{hostname}{port}"


def _evaluate_on_existing_pages(
    pages: list[Page],
    scripts: list[str],
) -> None:
    """Best-effort run of *scripts* on already-open pages.

    Persistent contexts may restore tabs pointing at ``chrome://``,
    extension pages, or already-closed pages.  Scripts are already
    registered via ``add_init_script`` for future navigations, so
    failures here are non-fatal.

    "Target closed" errors are silently swallowed (expected for
    crashed/closed tabs).  Other errors are logged at warning level
    so they surface in logs without aborting session startup.
    """
    for page in pages:
        if page.is_closed():
            continue
        try:
            url = page.url
        except PlaywrightError as exc:
            if _is_target_closed(exc):
                continue
            raise
        if any(url.startswith(prefix) for prefix in _UNSAFE_URL_PREFIXES):
            logger.debug("Skipping init-script injection on %s", url)
            continue
        origin = _safe_origin(url)
        for script in scripts:
            try:
                page.evaluate(script)
            except PlaywrightError as exc:
                if _is_target_closed(exc):
                    logger.debug("Page closed during init-script injection")
                    break
                logger.warning(
                    "Init-script injection failed on %s (%s)",
                    origin,
                    type(exc).__name__,
                )
            except Exception as exc:
                logger.warning(
                    "Init-script injection failed on %s (%s)",
                    origin,
                    type(exc).__name__,
                )


class BrowserSession:
    """Context manager for a persistent Chrome browser session.

    Uses system Chrome (``channel="chrome"``) and stores session data
    in a persistent profile directory so SSO cookies survive between runs.

    Args:
        headed: Show the browser window. Use for first-time SSO login.
        profile_dir: Browser profile directory for session persistence.
        viewport: Browser viewport dimensions.
        enable_extensions: Load Chrome extensions from the profile.
            Only works in headed mode; Playwright ignores extensions
            when headless.
        init_scripts: Additional JavaScript snippets to inject into
            every page via ``add_init_script``.
        skip_duo_update_prompt: Inject a script that auto-dismisses
            the Duo "update Chrome" nag. Disable for manual flows
            where you want full control of the Duo page.
    """

    def __init__(  # noqa: PLR0913  -- all params are keyword-only with defaults
        self,
        *,
        headed: bool = False,
        profile_dir: str | Path | None = None,
        viewport: dict[str, int] | None = None,
        enable_extensions: bool = False,
        init_scripts: list[str] | None = None,
        skip_duo_update_prompt: bool = True,
    ) -> None:
        self._headed = headed
        self._profile = Path(profile_dir) if profile_dir else DEFAULT_PROFILE_DIR
        self._viewport = viewport or _DEFAULT_VIEWPORT
        self._enable_extensions = enable_extensions
        self._init_scripts = list(init_scripts) if init_scripts else []
        self._skip_duo_update_prompt = skip_duo_update_prompt
        self._pw: Playwright | None = None
        self._context: BrowserContext | None = None

    def __enter__(self) -> BrowserSession:
        self._profile.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()

        launch_kwargs: dict[str, object] = {
            "user_data_dir": str(self._profile),
            "channel": "chrome",
            "headless": not self._headed,
            "accept_downloads": False,
            "viewport": self._viewport,
        }

        if self._enable_extensions:
            launch_kwargs["ignore_default_args"] = ["--disable-extensions"]

        try:
            self._context = self._pw.chromium.launch_persistent_context(
                **launch_kwargs,  # type: ignore[arg-type]
            )

            all_scripts: list[str] = []
            if self._skip_duo_update_prompt:
                all_scripts.append(DUO_SKIP_UPDATE_SCRIPT)
            all_scripts.extend(self._init_scripts)

            for script in all_scripts:
                self._context.add_init_script(script)

            _evaluate_on_existing_pages(self._context.pages, all_scripts)
        except Exception:
            if self._pw is not None:
                try:
                    self._pw.stop()
                finally:
                    self._pw = None
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if self._context:
                self._context.close()
        finally:
            if self._pw:
                self._pw.stop()
            self._context = None
            self._pw = None

    @property
    def context(self) -> BrowserContext:
        """The underlying Playwright browser context."""
        if self._context is None:
            msg = "BrowserSession is not active. Use as a context manager."
            raise RuntimeError(msg)
        return self._context

    def new_page(self) -> Page:
        """Open a new browser tab."""
        return self.context.new_page()

    @staticmethod
    def is_auth_redirect(current_url: str, target_url: str) -> bool:
        """Check if the browser is on an SSO page instead of the target."""
        return is_auth_redirect(current_url, target_url)

    @staticmethod
    def wait_for_login(
        page: Page,
        target_url: str,
        timeout_ms: int | None = None,
    ) -> None:
        """Block until SSO completes and the browser returns to the target."""
        if timeout_ms is not None:
            wait_for_login(page, target_url, timeout_ms=timeout_ms)
        else:
            wait_for_login(page, target_url)
