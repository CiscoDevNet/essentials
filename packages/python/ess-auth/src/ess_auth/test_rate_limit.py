"""Tests for rate-limit header parsing and the hold policy.

The header names and the example values follow the convention published by
Okta-backed identity platforms: ``X-Rate-Limit-Limit``,
``X-Rate-Limit-Remaining``, and ``X-Rate-Limit-Reset`` (UTC epoch seconds).
"""

from __future__ import annotations

import httpx
import pytest

from ess_auth.rate_limit import (
    RateLimitStatus,
    diagnostic_headers,
    parse_rate_limit_headers,
    rate_limit_hold_secs,
)

_NOW = 1_516_307_536.0
_RESET = 1_516_307_596  # sixty seconds after _NOW


def _headers(**values: str) -> httpx.Headers:
    return httpx.Headers({k.replace("_", "-"): v for k, v in values.items()})


class TestParse:
    def test_reads_the_okta_headers(self) -> None:
        status = parse_rate_limit_headers(
            _headers(
                X_Rate_Limit_Limit="60",
                X_Rate_Limit_Remaining="35",
                X_Rate_Limit_Reset=str(_RESET),
            ),
            now_epoch=_NOW,
        )

        assert status == RateLimitStatus(
            limit=60, remaining=35, reset_epoch=float(_RESET)
        )
        assert status.is_reported()

    def test_absent_headers_report_nothing(self) -> None:
        status = parse_rate_limit_headers(httpx.Headers(), now_epoch=_NOW)

        assert not status.is_reported()

    def test_malformed_values_are_ignored_not_raised(self) -> None:
        status = parse_rate_limit_headers(
            _headers(X_Rate_Limit_Limit="lots", X_Rate_Limit_Remaining="-3"),
            now_epoch=_NOW,
        )

        assert status.limit is None
        assert status.remaining is None

    @pytest.mark.parametrize("raw", ["inf", "1e999", "nan", "-inf"])
    def test_non_finite_values_are_ignored_not_raised(self, raw: str) -> None:
        """An upstream header must never abort token acquisition."""
        status = parse_rate_limit_headers(
            _headers(
                X_Rate_Limit_Limit=raw,
                X_Rate_Limit_Remaining=raw,
                X_Rate_Limit_Reset=raw,
                Retry_After=raw,
            ),
            now_epoch=_NOW,
        )

        assert not status.is_reported()

    def test_retry_after_seconds(self) -> None:
        status = parse_rate_limit_headers(_headers(Retry_After="17"), now_epoch=_NOW)

        retry_after = 17.0
        assert status.retry_after_secs == retry_after

    def test_retry_after_http_date(self) -> None:
        # 2018-01-18T20:33:16Z is _RESET.
        status = parse_rate_limit_headers(
            _headers(Retry_After="Thu, 18 Jan 2018 20:33:16 GMT"), now_epoch=_NOW
        )

        assert status.retry_after_secs == pytest.approx(60.0)


class TestHold:
    def test_healthy_budget_does_not_hold(self) -> None:
        status = RateLimitStatus(limit=60, remaining=35, reset_epoch=_RESET)

        assert rate_limit_hold_secs(status, status_code=200, now_epoch=_NOW) == 0.0

    def test_nearly_spent_budget_holds_until_reset(self) -> None:
        """Stop before the shared egress budget runs out, not after."""
        status = RateLimitStatus(limit=60, remaining=6, reset_epoch=_RESET)

        hold = rate_limit_hold_secs(status, status_code=200, now_epoch=_NOW)

        assert hold == pytest.approx(60.0)

    def test_reserve_is_never_below_one_request(self) -> None:
        """A tiny limit still keeps the last request in hand."""
        status = RateLimitStatus(limit=5, remaining=1, reset_epoch=_RESET)

        hold = rate_limit_hold_secs(
            status, status_code=200, now_epoch=_NOW, reserve_fraction=0.0
        )

        assert hold > 0

    def test_429_holds_until_reset(self) -> None:
        status = RateLimitStatus(limit=60, remaining=0, reset_epoch=_RESET)

        hold = rate_limit_hold_secs(status, status_code=429, now_epoch=_NOW)

        assert hold == pytest.approx(60.0)

    def test_429_stale_reset_does_not_cancel_retry_after(self) -> None:
        """A reset skewed into the past must not drop an explicit wait."""
        status = RateLimitStatus(
            limit=60, remaining=0, reset_epoch=_NOW - 30, retry_after_secs=45.0
        )

        hold = rate_limit_hold_secs(status, status_code=429, now_epoch=_NOW)

        retry_after = 45.0
        assert hold == retry_after

    def test_429_waits_for_the_longer_of_reset_and_retry_after(self) -> None:
        status = RateLimitStatus(
            limit=60, remaining=0, reset_epoch=_RESET, retry_after_secs=10.0
        )

        hold = rate_limit_hold_secs(status, status_code=429, now_epoch=_NOW)

        assert hold == pytest.approx(60.0)

    def test_429_without_reset_uses_retry_after(self) -> None:
        status = RateLimitStatus(retry_after_secs=12.0)

        hold = rate_limit_hold_secs(status, status_code=429, now_epoch=_NOW)

        retry_after = 12.0
        assert hold == retry_after

    def test_hold_is_capped(self) -> None:
        """A bogus reset far in the future must not park callers forever."""
        status = RateLimitStatus(limit=60, remaining=0, reset_epoch=_NOW + 10**9)

        hold = rate_limit_hold_secs(
            status, status_code=429, now_epoch=_NOW, max_hold_secs=3600.0
        )

        cap = 3600.0
        assert hold == cap

    def test_reset_in_the_past_does_not_hold(self) -> None:
        status = RateLimitStatus(limit=60, remaining=0, reset_epoch=_NOW - 5)

        assert rate_limit_hold_secs(status, status_code=200, now_epoch=_NOW) == 0.0

    def test_reserve_fraction_is_tunable_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("API_RATE_LIMIT_RESERVE_FRACTION", "0.5")
        status = RateLimitStatus(limit=60, remaining=25, reset_epoch=_RESET)

        assert rate_limit_hold_secs(status, status_code=200, now_epoch=_NOW) > 0


class TestDiagnosticHeaders:
    def test_keeps_request_ids_and_budget(self) -> None:
        headers = _headers(
            X_Okta_Request_Id="abc123",
            X_Rate_Limit_Remaining="0",
            Akamai_GRN="0.1234.5678",
        )

        assert diagnostic_headers(headers) == {
            "x-okta-request-id": "abc123",
            "akamai-grn": "0.1234.5678",
            "x-rate-limit-remaining": "0",
        }

    def test_never_copies_credentials_or_cookies(self) -> None:
        headers = _headers(Set_Cookie="sid=secret", Authorization="Bearer secret")

        assert diagnostic_headers(headers) == {}
