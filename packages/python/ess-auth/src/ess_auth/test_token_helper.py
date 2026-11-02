"""Tests for the sync token helper's cooldown and scope behaviour.

The cooldown exists because of an observed production incident: a denied
token request was not cached, so every subsequent caller retried immediately
against an endpoint that rate-limits per source IP, turning an intermittent
denial into a sustained one.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest

from ess_auth import token_helper
from ess_auth.token_helper import (
    AuthenticationError,
    TokenEndpointCoolingDownError,
    TokenHelper,
    TokenRequestFailedError,
)


def _client(
    captured: list[httpx.Request],
    *,
    status: int = 200,
    body: dict[str, Any] | None,
    response_headers: dict[str, str] | None = None,
) -> httpx.Client:
    """Return an httpx.Client whose transport records and canned-responds."""
    payload = body if body is not None else {"access_token": "tok", "expires_in": 3600}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            status,
            content=json.dumps(payload).encode(),
            headers={"content-type": "application/json", **(response_headers or {})},
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def _helper(**kwargs: Any) -> TokenHelper:
    return TokenHelper("cid", "sec", token_url="https://idp.example.com/token", **kwargs)


class TestCooldown:
    def test_failure_suppresses_the_next_request(self) -> None:
        captured: list[httpx.Request] = []
        helper = _helper()
        http = _client(captured, status=403, body={"error": "access_denied"})

        with pytest.raises(TokenRequestFailedError):
            helper.fetch_token(http)
        with pytest.raises(TokenEndpointCoolingDownError):
            helper.fetch_token(http)

        # The second call never reached the endpoint.
        assert len(captured) == 1

    def test_cooldown_expiry_allows_another_attempt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[httpx.Request] = []
        helper = _helper()
        http = _client(captured, status=403, body={"error": "access_denied"})

        clock = {"now": 1000.0}
        monkeypatch.setattr("ess_auth.cooldown.time.monotonic", lambda: clock["now"])
        monkeypatch.setattr(token_helper.time, "monotonic", lambda: clock["now"])

        with pytest.raises(TokenRequestFailedError):
            helper.fetch_token(http)

        clock["now"] = 1030.0  # still inside the window
        with pytest.raises(TokenEndpointCoolingDownError):
            helper.fetch_token(http)

        clock["now"] = 1100.0  # clear of the jittered window (<=72s)
        with pytest.raises(TokenRequestFailedError):
            helper.fetch_token(http)

        denied_then_retried = 2
        assert len(captured) == denied_then_retried

    def test_success_clears_the_cooldown(self) -> None:
        helper = _helper()
        denied: list[httpx.Request] = []
        with pytest.raises(TokenRequestFailedError):
            helper.fetch_token(_client(denied, status=403, body={"e": "x"}))

        # A fresh helper state would hide a stuck cooldown, so reuse this one.
        helper._cooldown.clear()  # noqa: SLF001 -- simulating the window passing
        granted: list[httpx.Request] = []
        assert helper.fetch_token(_client(granted, body=None)) == "tok"
        assert helper._cooldown.remaining() == 0.0  # noqa: SLF001

    def test_concurrent_threads_make_one_request(self) -> None:
        """The cooldown caps attempts per client, so the check must be atomic.

        Two worker threads on a cold cache can otherwise both observe a
        closed breaker before either failure opens it, and both reach the
        endpoint the cooldown is meant to shield.
        """
        captured: list[httpx.Request] = []
        helper = _helper()
        started = threading.Barrier(2)

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            # Widen the window in which an unserialised second caller would
            # still see a closed breaker, so the regression cannot pass by
            # winning a microsecond-wide race.
            time.sleep(0.05)
            return httpx.Response(
                403,
                content=json.dumps({"error": "access_denied"}).encode(),
                headers={"content-type": "application/json"},
            )

        http = httpx.Client(transport=httpx.MockTransport(handler))

        errors: list[Exception] = []

        def _attempt() -> None:
            try:
                started.wait(timeout=5)
                helper.fetch_token(http)
            except AuthenticationError:
                # Either a live refusal (the winner) or a suppressed
                # attempt (the loser); both are the expected outcome.
                pass
            except Exception as exc:  # noqa: BLE001 -- surfaced in the main thread
                errors.append(exc)

        threads = [threading.Thread(target=_attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
            # A worker that hung or died would leave the request-count
            # assertion below trivially satisfied, so check it landed.
            assert not thread.is_alive(), "worker thread did not finish"
        assert errors == [], f"worker raised unexpectedly: {errors}"

        # The loser of the race is refused by the cooldown, not the endpoint.
        assert len(captured) == 1


class TestCaching:
    def test_short_lived_token_is_still_cached(self) -> None:
        """A lifetime at or below the refresh margin must not defeat the cache.

        Treating such a token as expired on arrival means one token request
        per call, which is the amplification the cooldown exists to stop.
        """
        captured: list[httpx.Request] = []
        helper = _helper(refresh_margin=120)
        http = _client(captured, body={"access_token": "tok", "expires_in": 30})

        assert helper.fetch_token(http) == "tok"
        assert helper.fetch_token(http) == "tok"
        assert len(captured) == 1

    @pytest.mark.parametrize("expires_in", [0, -1])
    def test_already_expired_token_is_rejected(self, expires_in: int) -> None:
        """A dead token must not be cached by the minimum-lifetime floor.

        The floor keeps a short-but-valid token usable; it must not make
        an already-expired one look usable for a second.
        """
        helper = _helper()
        http = _client([], body={"access_token": "tok", "expires_in": expires_in})

        with pytest.raises(TokenRequestFailedError):
            helper.fetch_token(http)
        # Treated like any other unusable response: the breaker is open.
        assert helper._cooldown.remaining() > 0  # noqa: SLF001 -- cooldown under test


class TestErrorDetail:
    """Coverage for the shared summarizer.

    ``error_detail`` lives alongside the sync helper and is used by the async
    one too, so its behaviour is pinned down here once.
    """

    def test_prefers_the_oauth_error_fields(self) -> None:
        response = httpx.Response(
            403,
            json={"error": "invalid_scope", "error_description": "bad scope"},
        )

        assert token_helper.error_detail(response) == "invalid_scope bad scope"

    def test_falls_back_to_raw_text_for_non_json(self) -> None:
        """An edge proxy denial is HTML, not an OAuth error body."""
        response = httpx.Response(403, text="<html>  Forbidden\n by edge </html>")

        # Whitespace is collapsed so the excerpt stays one log-friendly line.
        assert token_helper.error_detail(response) == "<html> Forbidden by edge </html>"

    def test_is_truncated_to_the_cap(self) -> None:
        response = httpx.Response(403, text="x" * 1000)

        detail = token_helper.error_detail(response)

        assert len(detail) == token_helper._ERROR_DETAIL_MAX_CHARS  # noqa: SLF001 -- cap under test


class TestMalformedResponses:
    @pytest.mark.parametrize("access_token", ["", None, 12345])
    def test_unusable_access_token_is_rejected(self, access_token: object) -> None:
        """An empty or non-string token must not be cached.

        It would otherwise clear the cooldown and leave callers sending
        ``Bearer`` followed by nothing useful.
        """
        helper = _helper()
        http = _client([], body={"access_token": access_token, "expires_in": 3600})

        with pytest.raises(TokenRequestFailedError):
            helper.fetch_token(http)
        assert helper._cooldown.remaining() > 0  # noqa: SLF001 -- cooldown under test

    def test_malformed_2xx_honours_a_spent_rate_limit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A spent budget on an unusable 2xx must hold until the reset.

        The generic failure window is ~60s; the reset here is 10 minutes out.
        """
        now_epoch = 1_700_000_000.0
        monkeypatch.setattr("ess_auth.rate_limit.time.time", lambda: now_epoch)
        helper = _helper()
        http = _client(
            [],
            body={"access_token": "", "expires_in": 3600},
            response_headers={
                "X-Rate-Limit-Limit": "60",
                "X-Rate-Limit-Remaining": "0",
                "X-Rate-Limit-Reset": str(int(now_epoch + 600)),
            },
        )

        with pytest.raises(TokenRequestFailedError):
            helper.fetch_token(http)

        first_window_ceiling = 72.0
        assert helper._cooldown.remaining() > first_window_ceiling  # noqa: SLF001


class TestFailureDetail:
    def test_status_and_detail_are_exposed_for_caller_logging(self) -> None:
        """Callers log their own context; they should not re-read the response."""
        helper = _helper()
        http = _client([], status=403, body={"error": "access_denied"})

        with pytest.raises(TokenRequestFailedError) as err:
            helper.fetch_token(http)

        forbidden = 403
        assert err.value.status_code == forbidden
        assert "access_denied" in err.value.detail

    def test_request_id_is_exposed_for_upstream_support(self) -> None:
        helper = _helper()
        http = _client(
            [],
            status=403,
            body={"error": "access_denied"},
            response_headers={"X-Okta-Request-Id": "req-123"},
        )

        with pytest.raises(TokenRequestFailedError) as err:
            helper.fetch_token(http)

        assert err.value.diagnostics == {"x-okta-request-id": "req-123"}


class TestFullTokenLifetime:
    def test_stale_token_is_served_when_refresh_is_denied(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        clock = {"now": 1000.0}
        monkeypatch.setattr("ess_auth.cooldown.time.monotonic", lambda: clock["now"])
        helper = _helper(refresh_margin=60)
        assert helper.fetch_token(_client([], body=None)) == "tok"

        denied: list[httpx.Request] = []
        clock["now"] = 1000.0 + 3600 - 30  # inside the margin, before expiry
        http = _client(denied, status=403, body={"error": "x"})

        assert helper.fetch_token(http) == "tok"
        assert helper.fetch_token(http) == "tok"
        assert len(denied) == 1

    def test_expired_token_is_not_served(self, monkeypatch: pytest.MonkeyPatch) -> None:
        clock = {"now": 1000.0}
        monkeypatch.setattr("ess_auth.cooldown.time.monotonic", lambda: clock["now"])
        helper = _helper(refresh_margin=60)
        helper.fetch_token(_client([], body=None))

        clock["now"] = 1000.0 + 3600 + 1
        with pytest.raises(TokenRequestFailedError):
            helper.fetch_token(_client([], status=403, body={"error": "x"}))


class TestClientIdentification:
    def test_identification_header_comes_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OAUTH_TOKEN_CLIENT_HEADER_NAME", "X-Client-App")
        monkeypatch.setenv("OAUTH_TOKEN_CLIENT_HEADER_VALUE", "agreed")
        captured: list[httpx.Request] = []

        _helper().fetch_token(_client(captured, body=None))

        assert captured[0].headers["X-Client-App"] == "agreed"


class TestScope:
    def test_scope_is_sent_when_set(self) -> None:
        captured: list[httpx.Request] = []
        helper = _helper(scope="example-scope")
        helper.fetch_token(_client(captured, body=None))

        form = parse_qs(captured[0].content.decode())
        assert form["scope"] == ["example-scope"]

    def test_scope_is_omitted_when_empty(self) -> None:
        """Some authorization servers reject an empty scope parameter."""
        captured: list[httpx.Request] = []
        helper = _helper()
        helper.fetch_token(_client(captured, body=None))

        assert "scope" not in parse_qs(captured[0].content.decode())
