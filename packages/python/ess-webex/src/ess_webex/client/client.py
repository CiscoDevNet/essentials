"""Webex client wrapping wxc_sdk.WebexSimpleApi."""

from __future__ import annotations

import os
from itertools import islice

from wxc_sdk import WebexSimpleApi


class WebexAuthError(Exception):
    """Raised when Webex authentication fails."""


def _to_dict(obj: object, keys: list[str]) -> dict:
    """Extract named attributes from an SDK object into a plain dict."""
    return {k: getattr(obj, k, None) for k in keys}


_ROOM_KEYS = [
    "id",
    "title",
    "team_id",
    "type",
    "last_activity",
    "creator_id",
    "created",
    "is_locked",
    "is_read_only",
]
_TEAM_KEYS = ["id", "name", "description", "created"]
_MESSAGE_KEYS = [
    "id",
    "room_id",
    "person_id",
    "person_email",
    "text",
    "markdown",
    "created",
]
_MEETING_KEYS = [
    "id",
    "title",
    "start",
    "end",
    "timezone",
    "host_email",
    "meeting_type",
    "state",
]


class WebexClient:
    """High-level interface to Webex via wxc-sdk."""

    def __init__(self, access_token: str | None = None) -> None:
        token = access_token or os.environ.get("WEBEX_ACCESS_TOKEN")
        if not token:
            msg = (
                "No Webex access token. Set WEBEX_ACCESS_TOKEN in "
                "your environment or .env file."
            )
            raise WebexAuthError(msg)
        self._api = WebexSimpleApi(tokens=token)

    # -- Rooms --

    def list_rooms(
        self,
        *,
        max_results: int = 25,
        type_: str | None = None,
        team_id: str | None = None,
        sort_by: str | None = "lastactivity",
    ) -> list[dict]:
        """List rooms/spaces the authenticated user belongs to."""
        kwargs: dict = {}
        if type_:
            kwargs["type_"] = type_
        if team_id:
            kwargs["team_id"] = team_id
        if sort_by:
            kwargs["sort_by"] = sort_by
        rooms = islice(self._api.rooms.list(**kwargs), max_results)
        return [_to_dict(r, _ROOM_KEYS) for r in rooms]

    def get_room(self, room_id: str) -> dict:
        """Get details of a single room."""
        return _to_dict(self._api.rooms.details(room_id), _ROOM_KEYS)

    # -- Teams --

    def list_teams(self, *, max_results: int = 25) -> list[dict]:
        """List teams the authenticated user belongs to."""
        teams = islice(self._api.teams.list(), max_results)
        return [_to_dict(t, _TEAM_KEYS) for t in teams]

    def get_team(self, team_id: str) -> dict:
        """Get details of a single team."""
        return _to_dict(self._api.teams.details(team_id), _TEAM_KEYS)

    # -- Messages --

    def list_messages(self, room_id: str, *, max_results: int = 25) -> list[dict]:
        """List recent messages in a room, newest first."""
        msgs = islice(self._api.messages.list(room_id=room_id), max_results)
        return [_to_dict(m, _MESSAGE_KEYS) for m in msgs]

    def get_message(self, message_id: str) -> dict:
        """Get a single message by ID."""
        return _to_dict(self._api.messages.details(message_id), _MESSAGE_KEYS)

    def send_message(
        self,
        text: str,
        *,
        room_id: str | None = None,
        to_person_email: str | None = None,
        markdown: str | None = None,
    ) -> dict:
        """Send a message to a room or direct to a person."""
        if not room_id and not to_person_email:
            msg = "Provide room_id or to_person_email"
            raise ValueError(msg)
        kwargs: dict = {"text": text}
        if room_id:
            kwargs["room_id"] = room_id
        if to_person_email:
            kwargs["to_person_email"] = to_person_email
        if markdown:
            kwargs["markdown"] = markdown
        msg = self._api.messages.create(**kwargs)
        return _to_dict(msg, _MESSAGE_KEYS)

    # -- Meetings --

    def list_meetings(
        self,
        *,
        from_: str | None = None,
        to_: str | None = None,
        max_results: int = 25,
    ) -> list[dict]:
        """List meetings in a date range."""
        kwargs: dict = {}
        if from_:
            kwargs["from_"] = from_
        if to_:
            kwargs["to_"] = to_
        meetings = islice(self._api.meetings.list(**kwargs), max_results)
        return [_to_dict(m, _MEETING_KEYS) for m in meetings]

    def get_meeting(self, meeting_id: str) -> dict:
        """Get details of a single meeting."""
        return _to_dict(self._api.meetings.get(meeting_id), _MEETING_KEYS)

    def create_meeting(
        self,
        title: str,
        start: str,
        end: str,
        *,
        invitees: list[str] | None = None,
    ) -> dict:
        """Create a meeting."""
        kwargs: dict = {"title": title, "start": start, "end": end}
        if invitees:
            kwargs["invitees"] = [{"email": e} for e in invitees]
        meeting = self._api.meetings.create(**kwargs)
        return _to_dict(meeting, _MEETING_KEYS)
