"""Domain exceptions for browser sessions and SSO flows."""

from __future__ import annotations

HEADED_HINT = " Re-run with --headed to complete login in the browser."


class EssBrowserError(Exception):
    """Base class for every error raised by this package."""


class SsoTimeoutError(EssBrowserError):
    """SSO did not complete before the login timeout elapsed."""


def sso_timeout_message(
    *,
    headed: bool,
    prefix: str = "SSO authentication timed out",
    retry_hint: str = HEADED_HINT,
) -> str:
    """Build the message for an SSO login that never completed.

    Args:
        headed: Whether the browser window was already visible. The retry
            hint is appended only when it was not, because an interactive
            login cannot be completed in a headless window.
        prefix: Leading sentence, so a caller can name its own IdP.
        retry_hint: How *this* caller's CLI asks for a visible window.
            Defaults to ``--headed``; a tool spelling it differently must
            pass its own, or it sends operators to a flag it lacks.

    Returns:
        The message, with the retry hint appended only when actionable.
    """
    hint = "" if headed else retry_hint
    return f"{prefix}.{hint}"
