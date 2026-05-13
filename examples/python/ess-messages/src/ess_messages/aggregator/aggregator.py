"""Fetch and merge messages from email and Webex into AS2 activities."""

from __future__ import annotations

from activitystreams2 import Create

from ..normalize import normalize_email, normalize_webex, sort_key


class MessageAggregator:
    """Aggregates messages from Outlook and Webex clients."""

    def __init__(self, outlook_client=None, webex_client=None) -> None:
        self._outlook = outlook_client
        self._webex = webex_client

    def get_latest(
        self,
        *,
        limit: int = 25,
        webex_room_ids: list[str] | None = None,
        email_only: bool = False,
        webex_only: bool = False,
    ) -> list[Create]:
        """Fetch, normalize, merge, and sort messages.

        Returns up to *limit* AS2 Create activities, newest first.
        """
        activities: list[Create] = []

        if not webex_only and self._outlook:
            activities.extend(self._fetch_emails(limit))

        if not email_only and self._webex:
            activities.extend(self._fetch_webex(limit, webex_room_ids))

        activities.sort(key=sort_key, reverse=True)
        return activities[:limit]

    def _fetch_emails(self, limit: int) -> list[Create]:
        messages = self._outlook.list_messages(limit=limit)
        return [normalize_email(msg) for msg in messages]

    def _fetch_webex(self, limit: int, room_ids: list[str] | None) -> list[Create]:
        if room_ids is None:
            rooms = self._webex.list_rooms(max_results=5)
            room_ids = [r["id"] for r in rooms]

        activities: list[Create] = []
        per_room = max(limit // len(room_ids), 1) if room_ids else 0
        for room_id in room_ids:
            room = self._webex.get_room(room_id)
            room_title = room.get("title", "")
            messages = self._webex.list_messages(room_id, max_results=per_room)
            activities.extend(normalize_webex(msg, room_title) for msg in messages)
        return activities
