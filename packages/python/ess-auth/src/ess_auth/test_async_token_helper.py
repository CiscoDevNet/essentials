"""Tests for the async token helper.

Style note: synchronous pytest driving ``asyncio.run`` on a fresh loop per
test, mirroring how LangGraph creates a loop per request. Re-using one loop
would mask the cross-loop lock regression these tests protect.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest

from ess_auth import AsyncTokenHelper, TokenClientOptions
from ess_auth.token_helper import (
    TokenEndpointCoolingDownError,
    TokenRequestFailedError,
)


def _patch_transport(
    monkeypatch: pytest.MonkeyPatch,
    *,
    status: int = 200,
    body: dict[str, Any] | None = None,
    response_headers: dict[str, str] | None = None,
) -> list[httpx.Request]:
    """Replace ``httpx.AsyncClient`` with a stub recording every request."""
    captured: list[httpx.Request] = []
    payload = body if body is not None else {"access_token": "tok", "expires_in": 3600}

    class _StubClient:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> _StubClient:
            return self

        async def __aexit__(self, *_exc: Any) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> httpx.Response:
            request = httpx.Request(
                "POST", url, data=kwargs.get("data"), headers=kwargs.get("headers")
            )
            captured.append(request)
            # Yield like a real network call would. Without this the holder
            # never suspends, so a second caller finds the lock free, never
            # waits on it, and the lock never binds to a loop -- which is
            # the only state the per-loop tests below are about.
            await asyncio.sleep(0)
            return httpx.Response(
                status,
                request=request,
                content=json.dumps(payload).encode(),
                headers={
                    "content-type": "application/json",
                    **(response_headers or {}),
                },
            )

    monkeypatch.setattr("ess_auth.async_token_helper.httpx.AsyncClient", _StubClient)
    return captured


def _run_on_fresh_loop(factory: Callable[[], Any]) -> Any:
    """Run ``factory()`` on a brand-new event loop and close it."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(factory())
    finally:
        loop.close()


def _helper(**kwargs: Any) -> AsyncTokenHelper:
    return AsyncTokenHelper(
        "cid",
        "sec",
        token_url="https://idp.example.com/token",
        options=TokenClientOptions(label="test", **kwargs),
    )


class TestCaching:
    def test_concurrent_callers_share_one_network_refresh(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = _patch_transport(monkeypatch)
        helper = _helper()

        async def _exercise() -> tuple[str, str]:
            return await asyncio.gather(helper.fetch_token(), helper.fetch_token())

        first, second = _run_on_fresh_loop(_exercise)
        assert first == second == "tok"
        assert len(captured) == 1

    def test_refresh_succeeds_across_two_event_loops(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A module-scoped helper outlives the loop that first used it.

        Guards the ``Lock is bound to a different event loop`` failure that
        motivated the per-loop lock cache. The lock only binds to a loop when
        a coroutine has to *wait* on it, so both loops must actually contend:
        each pair below is concurrent, and the cache is expired in between so
        the second pair refreshes rather than returning the first loop's
        token.
        """
        _patch_transport(monkeypatch)
        helper = _helper()

        async def _contend() -> Any:
            # gather() on a cold cache forces one caller to wait on the lock.
            return await asyncio.gather(helper.refresh(), helper.refresh())

        assert _run_on_fresh_loop(_contend) == ["tok", "tok"]

        # Expire the cache so the second loop cannot short-circuit via
        # _cached_token(); without this the lock is never contended twice and
        # the cross-loop regression would go unnoticed.
        helper._expires_at = 0.0  # noqa: SLF001 -- simulating token expiry

        assert _run_on_fresh_loop(_contend) == ["tok", "tok"]

    def test_short_lived_token_is_still_cached(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A lifetime at or below the refresh margin must not defeat the cache.

        Subtracting the margin unclamped puts the expiry in the past, so
        every caller refreshes and one token request per call returns --
        the amplification the cooldown exists to stop, through the cache.
        """
        captured = _patch_transport(
            monkeypatch, body={"access_token": "tok", "expires_in": 30}
        )
        helper = _helper(refresh_margin=120)

        async def _exercise() -> None:
            await helper.fetch_token()
            await helper.fetch_token()

        _run_on_fresh_loop(_exercise)
        assert len(captured) == 1

    @pytest.mark.parametrize("expires_in", [0, -1])
    def test_already_expired_token_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch, expires_in: int
    ) -> None:
        """A dead token must not be cached by the minimum-lifetime floor."""
        _patch_transport(
            monkeypatch, body={"access_token": "tok", "expires_in": expires_in}
        )
        helper = _helper()

        async def _exercise() -> None:
            with pytest.raises(TokenRequestFailedError):
                await helper.fetch_token()

        _run_on_fresh_loop(_exercise)
        # Treated like any other unusable response: the breaker is open.
        assert helper._cooldown.remaining() > 0  # noqa: SLF001 -- cooldown under test

    @pytest.mark.parametrize("access_token", ["", None, 12345])
    def test_unusable_access_token_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch, access_token: object
    ) -> None:
        """An empty or non-string token must not be cached."""
        _patch_transport(
            monkeypatch, body={"access_token": access_token, "expires_in": 3600}
        )
        helper = _helper()

        async def _exercise() -> None:
            with pytest.raises(TokenRequestFailedError):
                await helper.fetch_token()

        _run_on_fresh_loop(_exercise)
        assert helper._cooldown.remaining() > 0  # noqa: SLF001 -- cooldown under test


class TestLockCache:
    def test_closed_loops_are_evicted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A loop per request must not make the cache grow without bound.

        A contended ``asyncio.Lock`` strongly references its loop, so a
        cache holding locks by value would pin its own weak keys forever.
        """
        _patch_transport(monkeypatch)
        helper = _helper()

        async def _contend() -> Any:
            return await asyncio.gather(helper.refresh(), helper.refresh())

        for _ in range(3):
            _run_on_fresh_loop(_contend)
            helper._expires_at = 0.0  # noqa: SLF001 -- simulating token expiry

        assert len(helper._async_locks) <= 1  # noqa: SLF001 -- cache under test


class TestCooldown:
    def test_timeout_opens_the_cooldown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A hung endpoint is a failed attempt, not a free pass.

        ``asyncio.wait_for`` fires outside ``_do_refresh``, so the failure
        has to be recorded in ``refresh`` itself or the next caller starts
        a fresh attempt against an endpoint already known to be stuck.
        """

        class _HangingClient:
            def __init__(self, *_args: Any, **_kwargs: Any) -> None:
                pass

            async def __aenter__(self) -> _HangingClient:
                return self

            async def __aexit__(self, *_exc: Any) -> None:
                return None

            async def post(self, _url: str, **_kwargs: Any) -> httpx.Response:
                await asyncio.sleep(3600)
                raise AssertionError("unreachable")

        monkeypatch.setattr(
            "ess_auth.async_token_helper.httpx.AsyncClient", _HangingClient
        )
        monkeypatch.setattr(
            "ess_auth.async_token_helper._DEFAULT_TOTAL_TIMEOUT_SECS", 0.01
        )
        helper = _helper()

        async def _exercise() -> None:
            with pytest.raises(TokenRequestFailedError):
                await helper.fetch_token()
            with pytest.raises(TokenEndpointCoolingDownError):
                await helper.fetch_token()

        _run_on_fresh_loop(_exercise)

    def test_failure_suppresses_the_next_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = _patch_transport(
            monkeypatch, status=403, body={"error": "access_denied"}
        )
        helper = _helper()

        async def _exercise() -> None:
            with pytest.raises(TokenRequestFailedError):
                await helper.fetch_token()
            with pytest.raises(TokenEndpointCoolingDownError):
                await helper.fetch_token()

        _run_on_fresh_loop(_exercise)
        assert len(captured) == 1

    def test_cooldown_expiry_allows_another_attempt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = _patch_transport(
            monkeypatch, status=403, body={"error": "access_denied"}
        )
        helper = _helper(cooldown_secs=60.0)
        clock = {"now": 1000.0}
        monkeypatch.setattr("ess_auth.cooldown.time.monotonic", lambda: clock["now"])

        async def _exercise() -> None:
            with pytest.raises(TokenRequestFailedError):
                await helper.fetch_token()
            clock["now"] = 1030.0
            with pytest.raises(TokenEndpointCoolingDownError):
                await helper.fetch_token()
            clock["now"] = 1100.0  # clear of the jittered window (<=72s)
            with pytest.raises(TokenRequestFailedError):
                await helper.fetch_token()

        _run_on_fresh_loop(_exercise)
        denied_then_retried = 2
        assert len(captured) == denied_then_retried


class TestFullTokenLifetime:
    """A failed proactive refresh must not throw away a still-valid token.

    Tokens refresh ``refresh_margin`` seconds early. Before this, a denial in
    that window failed the caller even though the cached token had time
    left, so every refresh denial became a user-visible tool failure.
    """

    def test_stale_token_is_served_when_refresh_is_denied(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        clock = {"now": 1000.0}
        monkeypatch.setattr("ess_auth.cooldown.time.monotonic", lambda: clock["now"])
        _patch_transport(monkeypatch)
        helper = _helper(refresh_margin=60)
        assert _run_on_fresh_loop(helper.fetch_token) == "tok"

        denied = _patch_transport(monkeypatch, status=403, body={"error": "x"})
        clock["now"] = 1000.0 + 3600 - 30  # inside the margin, before expiry

        assert _run_on_fresh_loop(helper.fetch_token) == "tok"
        assert len(denied) == 1
        # Still suppressed: the next caller gets the stale token, no request.
        assert _run_on_fresh_loop(helper.fetch_token) == "tok"
        assert len(denied) == 1

    def test_expired_token_is_not_served(self, monkeypatch: pytest.MonkeyPatch) -> None:
        clock = {"now": 1000.0}
        monkeypatch.setattr("ess_auth.cooldown.time.monotonic", lambda: clock["now"])
        _patch_transport(monkeypatch)
        helper = _helper(refresh_margin=60)
        _run_on_fresh_loop(helper.fetch_token)

        _patch_transport(monkeypatch, status=403, body={"error": "x"})
        clock["now"] = 1000.0 + 3600 + 1

        async def _exercise() -> None:
            with pytest.raises(TokenRequestFailedError):
                await helper.fetch_token()

        _run_on_fresh_loop(_exercise)


class TestRateLimitHeaders:
    def test_429_reset_extends_the_cooldown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Honour the server's reset rather than our shorter first window."""
        now_epoch = 1_700_000_000.0
        monkeypatch.setattr("ess_auth.rate_limit.time.time", lambda: now_epoch)
        _patch_transport(
            monkeypatch,
            status=429,
            body={"error": "too_many_requests"},
            response_headers={
                "X-Rate-Limit-Limit": "60",
                "X-Rate-Limit-Remaining": "0",
                "X-Rate-Limit-Reset": str(int(now_epoch + 600)),
            },
        )
        helper = _helper(cooldown_secs=60.0)

        async def _exercise() -> None:
            with pytest.raises(TokenRequestFailedError):
                await helper.fetch_token()

        _run_on_fresh_loop(_exercise)
        first_window_ceiling = 72.0
        assert helper._cooldown.remaining() > first_window_ceiling  # noqa: SLF001

    def test_nearly_spent_budget_suppresses_the_next_refresh(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        now_epoch = 1_700_000_000.0
        monkeypatch.setattr("ess_auth.rate_limit.time.time", lambda: now_epoch)
        _patch_transport(
            monkeypatch,
            response_headers={
                "X-Rate-Limit-Limit": "60",
                "X-Rate-Limit-Remaining": "2",
                "X-Rate-Limit-Reset": str(int(now_epoch + 45)),
            },
        )
        helper = _helper()

        assert _run_on_fresh_loop(helper.fetch_token) == "tok"
        assert helper._cooldown.remaining() > 0  # noqa: SLF001
        assert helper._cooldown.consecutive_failures == 0  # noqa: SLF001

    def test_failure_carries_request_id_for_upstream_support(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_transport(
            monkeypatch,
            status=403,
            body={"error": "access_denied"},
            response_headers={"X-Okta-Request-Id": "req-123"},
        )
        helper = _helper()

        async def _exercise() -> TokenRequestFailedError:
            with pytest.raises(TokenRequestFailedError) as err:
                await helper.fetch_token()
            return err.value

        error = _run_on_fresh_loop(_exercise)
        assert error.diagnostics["x-okta-request-id"] == "req-123"


class TestClientIdentification:
    def test_identification_header_comes_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OAUTH_TOKEN_CLIENT_HEADER_NAME", "X-Client-App")
        monkeypatch.setenv("OAUTH_TOKEN_CLIENT_HEADER_VALUE", "agreed")
        captured = _patch_transport(monkeypatch)

        _run_on_fresh_loop(_helper().fetch_token)

        assert captured[0].headers["X-Client-App"] == "agreed"

    def test_explicit_headers_override_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OAUTH_TOKEN_CLIENT_HEADER_NAME", "X-Client-App")
        monkeypatch.setenv("OAUTH_TOKEN_CLIENT_HEADER_VALUE", "agreed")
        captured = _patch_transport(monkeypatch)

        _run_on_fresh_loop(_helper(request_headers={}).fetch_token)

        assert "X-Client-App" not in captured[0].headers


class TestClientAuthentication:
    def test_credentials_in_body_when_requested(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Some authorization servers want the credentials in the form body."""
        captured = _patch_transport(monkeypatch)
        helper = _helper(credentials_in_body=True)
        _run_on_fresh_loop(helper.fetch_token)

        form = parse_qs(captured[0].content.decode())
        assert form["client_id"] == ["cid"]
        assert form["client_secret"] == ["sec"]

    def test_basic_auth_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _patch_transport(monkeypatch)
        helper = _helper()
        _run_on_fresh_loop(helper.fetch_token)

        assert "client_secret" not in parse_qs(captured[0].content.decode())

    def test_scope_is_omitted_when_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _patch_transport(monkeypatch)
        _run_on_fresh_loop(_helper().fetch_token)

        assert "scope" not in parse_qs(captured[0].content.decode())
