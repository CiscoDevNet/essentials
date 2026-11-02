"""Tests for the edge identification header read from the environment."""

from __future__ import annotations

import logging

import pytest

from ess_auth.client_identity import (
    HEADER_NAME_ENV,
    HEADER_VALUE_ENV,
    client_identity_headers,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(HEADER_NAME_ENV, raising=False)
    monkeypatch.delenv(HEADER_VALUE_ENV, raising=False)


def test_unset_sends_nothing() -> None:
    assert client_identity_headers() == {}


def test_both_set_sends_the_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(HEADER_NAME_ENV, "X-Client-App")
    monkeypatch.setenv(HEADER_VALUE_ENV, "agreed-value")

    assert client_identity_headers() == {"X-Client-App": "agreed-value"}


def test_half_configured_sends_nothing_and_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(HEADER_NAME_ENV, "X-Client-App")

    with caplog.at_level(logging.WARNING):
        assert client_identity_headers() == {}
    assert HEADER_VALUE_ENV in caplog.text


@pytest.mark.parametrize("name", ["Authorization", "bad name", "X:Colon"])
def test_reserved_or_invalid_names_are_refused(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setenv(HEADER_NAME_ENV, name)
    monkeypatch.setenv(HEADER_VALUE_ENV, "agreed-value")

    assert client_identity_headers() == {}


def test_value_is_never_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(HEADER_NAME_ENV, "Authorization")
    monkeypatch.setenv(HEADER_VALUE_ENV, "agreed-value")

    with caplog.at_level(logging.DEBUG):
        client_identity_headers()
    assert "agreed-value" not in caplog.text
