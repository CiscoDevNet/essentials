"""Persistent Chrome browser session with SSO support."""

from __future__ import annotations

import json
import logging
import math
import os
import tempfile
import time
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

# Session cookies carried across launches by hand, because nothing else
# will. The cookie that represents a completed SSO login (often a
# `JSESSIONID` on the IdP's host) is session-scoped, and Chrome restores
# those only under "continue where you left off", which Playwright does
# not set. Without this, every launch starts logged out and re-runs the
# IdP round trip even though the profile is persistent.
#
# Only session-scoped cookies are written here. Anything with a real
# expiry already lives in Chrome's own store, and duplicating it would
# mean two sources of truth for the same cookie.
_SESSION_COOKIE_FILE = "session-cookies.json"

# Playwright's marker for "expires when the browser closes".
_SESSION_COOKIE_EXPIRY = -1

# Past this, a saved session is assumed dead and dropped rather than
# replayed. IdP sessions typically last a few hours, so a stale cookie
# would only fail -- but sending an old session identifier
# to the IdP is worth avoiding regardless.
_SESSION_COOKIE_MAX_AGE_S = 12 * 60 * 60

# Owner-only: these are live credentials for the duration of a session.
_SESSION_COOKIE_MODE = 0o600


def default_profile_dir(tool_name: str) -> Path:
    """Return the conventional profile directory for *tool_name*.

    Every consumer stores its session under ``~/.<tool>/browser-profile``.
    Separate directories per tool are deliberate: one expired session
    should not force a re-login everywhere.
    """
    return Path.home() / f".{tool_name}" / "browser-profile"


def profile_dir_display(tool_name: str) -> str:
    """Return the tilde form of :func:`default_profile_dir` for help text.

    Expanding the home directory in ``--help`` output bakes whichever
    username happens to run the command into docs and bug reports.
    """
    return f"~/.{tool_name}/browser-profile"


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


def _write_session_cookies(path: Path, cookies: list[dict]) -> None:
    """Write *cookies* to *path*, owner-readable only, atomically.

    Uses an exclusive temporary file (``mkstemp``) so a leftover
    ``session-cookies.json.tmp`` from a crash is never truncated and
    reused. ``mkstemp`` creates the file at ``0o600``; we chmod anyway
    so the mode is explicit.
    """
    payload = {"saved_at": time.time(), "cookies": cookies}
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, tmp_name = tempfile.mkstemp(
        prefix=f"{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    tmp = Path(tmp_name)
    replaced = False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        os.chmod(tmp, _SESSION_COOKIE_MODE)
        tmp.replace(path)
        replaced = True
    finally:
        if not replaced:
            tmp.unlink(missing_ok=True)


def _saved_at(payload: dict) -> float | None:
    """Return a finite save time, or nothing when the metadata is unusable.

    ``float("NaN")`` and ``float("inf")`` do not raise, and both fail the
    age comparison in the direction that would keep the cookies forever.
    """
    try:
        saved_at = float(payload.get("saved_at") or 0)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(saved_at):
        return None
    return saved_at


def _read_session_cookies(path: Path) -> list[dict]:
    """Return saved session cookies, or nothing when they cannot be used.

    A missing, unreadable, malformed, or stale file all mean the same
    thing to the caller: start without them and let SSO run.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError):
        logger.debug("Saved session cookies are unreadable; ignoring them")
        return []

    if not isinstance(payload, dict):
        return []

    saved_at = _saved_at(payload)
    if saved_at is None:
        logger.debug("Saved session cookies have invalid metadata; ignoring them")
        return []

    age = time.time() - saved_at
    if age > _SESSION_COOKIE_MAX_AGE_S:
        logger.debug("Saved session cookies are stale (%.0fs old); dropping", age)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.debug(
                "Could not drop stale session cookies (%s)", type(exc).__name__
            )
        return []

    cookies = payload.get("cookies")
    return cookies if isinstance(cookies, list) else []


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

            self._restore_session_cookies()
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
            # Before close: the cookies are gone once the context is.
            self._save_session_cookies()
            if self._context:
                self._context.close()
        finally:
            if self._pw:
                self._pw.stop()
            self._context = None
            self._pw = None

    @property
    def _session_cookie_path(self) -> Path:
        """Where this profile's session cookies are parked between runs."""
        return self._profile / _SESSION_COOKIE_FILE

    def _restore_session_cookies(self) -> None:
        """Re-add the session cookies saved by the previous run.

        Best effort throughout: a failure here costs one SSO login, so
        it must never stop the session from opening.
        """
        cookies = _read_session_cookies(self._session_cookie_path)
        if not cookies or self._context is None:
            return
        try:
            self._context.add_cookies(cookies)
        except (PlaywrightError, ValueError) as exc:
            logger.debug("Could not restore session cookies (%s)", type(exc).__name__)
            return
        logger.debug("Restored %d session cookie(s)", len(cookies))

    def _save_session_cookies(self) -> None:
        """Save session-scoped cookies so the next run stays logged in."""
        if self._context is None:
            return
        try:
            cookies = [
                cookie
                for cookie in self._context.cookies()
                if cookie.get("expires") == _SESSION_COOKIE_EXPIRY
            ]
        except PlaywrightError as exc:
            logger.debug("Could not read cookies to save (%s)", type(exc).__name__)
            return

        path = self._session_cookie_path
        if not cookies:
            # Nothing to carry over, and a leftover file from an earlier
            # run would outlive the session it belongs to. A failed delete
            # must not fail the session close.
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                logger.debug("Could not clear session cookies (%s)", type(exc).__name__)
            return

        try:
            _write_session_cookies(path, cookies)
        except OSError as exc:
            logger.debug("Could not save session cookies (%s)", type(exc).__name__)
            return
        logger.debug("Saved %d session cookie(s)", len(cookies))

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
    def is_auth_redirect(
        current_url: str,
        target_url: str,
        *,
        extra_auth_domains: tuple[str, ...] = (),
    ) -> bool:
        """Check if the browser is on an SSO page instead of the target.

        Args:
            current_url: Where the browser actually is.
            target_url: Where it was asked to go.
            extra_auth_domains: IdP host patterns to recognize in addition
                to :data:`~ess_browser.AUTH_DOMAINS`.
        """
        return is_auth_redirect(
            current_url,
            target_url,
            extra_auth_domains=extra_auth_domains,
        )

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
