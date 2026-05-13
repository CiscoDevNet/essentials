# ruff: noqa: PLR2004 -- magic numbers in test assertions are expected literals
"""Tests for WebexClient -- mocks wxc_sdk to avoid needing a token."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ess_webex.client import WebexAuthError, WebexClient


def _make_client() -> WebexClient:
    """Create a WebexClient with a fake token."""
    return WebexClient(access_token="fake-token")  # noqa: S106 -- test fixture token


def _room(**kwargs) -> SimpleNamespace:
    defaults = {
        "id": "room-1",
        "title": "General",
        "team_id": "team-1",
        "type": "group",
        "last_activity": "2026-04-10T10:00:00Z",
        "creator_id": "user-1",
        "created": "2026-01-01T00:00:00Z",
        "is_locked": False,
        "is_read_only": False,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _team(**kwargs) -> SimpleNamespace:
    defaults = {
        "id": "team-1",
        "name": "Engineering",
        "description": "Engineering team",
        "created": "2026-01-01T00:00:00Z",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _message(**kwargs) -> SimpleNamespace:
    defaults = {
        "id": "msg-1",
        "room_id": "room-1",
        "person_id": "user-1",
        "person_email": "alice@example.com",
        "text": "Hello world",
        "markdown": None,
        "created": "2026-04-10T10:00:00Z",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestListRooms:
    def test_returns_dicts(self):
        client = _make_client()
        rooms = iter([_room(), _room(id="room-2", title="Random")])
        client._api.rooms.list = MagicMock(return_value=rooms)
        result = client.list_rooms()

        assert len(result) == 2
        assert result[0]["id"] == "room-1"
        assert result[0]["title"] == "General"
        assert result[1]["id"] == "room-2"

    def test_filters_by_team(self):
        client = _make_client()
        client._api.rooms.list = MagicMock(return_value=iter([_room()]))
        client.list_rooms(team_id="team-1")

        client._api.rooms.list.assert_called_once_with(
            team_id="team-1", sort_by="lastactivity"
        )


class TestListTeams:
    def test_returns_dicts(self):
        client = _make_client()
        client._api.teams.list = MagicMock(return_value=iter([_team()]))
        result = client.list_teams()

        assert len(result) == 1
        assert result[0]["name"] == "Engineering"


class TestMessages:
    def test_list_messages(self):
        client = _make_client()
        client._api.messages.list = MagicMock(return_value=iter([_message()]))
        result = client.list_messages("room-1")

        assert len(result) == 1
        assert result[0]["text"] == "Hello world"

    def test_send_message(self):
        client = _make_client()
        client._api.messages.create = MagicMock(return_value=_message(id="msg-new"))
        result = client.send_message("Hi", room_id="room-1")

        assert result["id"] == "msg-new"
        client._api.messages.create.assert_called_once_with(text="Hi", room_id="room-1")


class TestMeetings:
    def test_list_meetings(self):
        meeting = SimpleNamespace(
            id="mtg-1",
            title="Standup",
            start="2026-04-10T09:00:00Z",
            end="2026-04-10T09:30:00Z",
            timezone="UTC",
            host_email="alice@example.com",
            meeting_type="scheduledMeeting",
            state="active",
        )
        client = _make_client()
        client._api.meetings.list = MagicMock(return_value=iter([meeting]))
        result = client.list_meetings()

        assert len(result) == 1
        assert result[0]["title"] == "Standup"


class TestAuth:
    def test_missing_token_raises(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(WebexAuthError),
        ):
            WebexClient()
