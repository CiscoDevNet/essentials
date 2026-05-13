# ruff: noqa: PLR2004 -- magic numbers in test assertions are expected literals
"""Tests for MessageAggregator -- mocks both clients."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from ess_messages.aggregator import MessageAggregator

_BASE_TIME = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)


def _email_msg(subject="Test email", minutes_ago=10):
    return {
        "id": f"email-{minutes_ago}",
        "subject": subject,
        "sender_name": "Alice",
        "sender_address": "alice@example.com",
        "date": _BASE_TIME - timedelta(minutes=minutes_ago),
        "is_read": True,
    }


def _webex_msg(text="Hello", minutes_ago=5):
    return {
        "id": f"webex-{minutes_ago}",
        "room_id": "room-1",
        "person_id": "user-1",
        "person_email": "bob@example.com",
        "text": text,
        "markdown": None,
        "created": _BASE_TIME - timedelta(minutes=minutes_ago),
    }


def _make_aggregator(emails=None, webex_msgs=None):
    outlook = MagicMock()
    outlook.list_messages.return_value = emails or []

    webex = MagicMock()
    webex.list_rooms.return_value = [{"id": "room-1"}]
    webex.get_room.return_value = {"title": "General"}
    webex.list_messages.return_value = webex_msgs or []

    return MessageAggregator(outlook_client=outlook, webex_client=webex)


class TestGetLatest:
    def test_merges_and_sorts_by_date(self):
        aggregator = _make_aggregator(
            emails=[_email_msg(minutes_ago=10)],
            webex_msgs=[_webex_msg(minutes_ago=5)],
        )
        results = aggregator.get_latest(limit=10)

        assert len(results) == 2
        assert results[0]["source"] == "webex"
        assert results[1]["source"] == "email"

    def test_respects_limit(self):
        aggregator = _make_aggregator(
            emails=[_email_msg(minutes_ago=i + 1) for i in range(10)],
            webex_msgs=[_webex_msg(minutes_ago=i + 1) for i in range(10)],
        )
        results = aggregator.get_latest(limit=5)

        assert len(results) == 5

    def test_email_only(self):
        aggregator = _make_aggregator(
            emails=[_email_msg()],
            webex_msgs=[_webex_msg()],
        )
        results = aggregator.get_latest(email_only=True)

        assert len(results) == 1
        assert results[0]["source"] == "email"

    def test_webex_only(self):
        aggregator = _make_aggregator(
            emails=[_email_msg()],
            webex_msgs=[_webex_msg()],
        )
        results = aggregator.get_latest(webex_only=True)

        assert len(results) == 1
        assert results[0]["source"] == "webex"

    def test_empty_sources(self):
        aggregator = _make_aggregator()
        results = aggregator.get_latest()

        assert results == []


class TestNormalization:
    def test_email_produces_as2(self):
        aggregator = _make_aggregator(emails=[_email_msg(subject="Q1 Report")])
        results = aggregator.get_latest(email_only=True, limit=1)

        activity = results[0]
        assert activity["source"] == "email"
        assert activity["actor"]["name"] == "Alice"
        assert activity["object"]["name"] == "Q1 Report"

    def test_webex_produces_as2(self):
        aggregator = _make_aggregator(webex_msgs=[_webex_msg(text="Hey team")])
        results = aggregator.get_latest(webex_only=True, limit=1)

        activity = results[0]
        assert activity["source"] == "webex"
        assert activity["actor"]["name"] == "bob@example.com"
        assert activity["object"]["content"] == "Hey team"
