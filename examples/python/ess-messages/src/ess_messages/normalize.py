"""Normalize email and Webex messages to Activity Streams 2.0."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from activitystreams2 import Create, Note, Person


def _ensure_datetime(value: object) -> datetime:
    """Coerce a value to a timezone-aware datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str) and value:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return datetime.min.replace(tzinfo=timezone.utc)


def normalize_email(msg: dict) -> Create:
    """Convert an Outlook GraphClient message dict to an AS2 Create activity."""
    actor = Person(name=msg.get("sender_name", ""))
    actor["id"] = f"mailto:{msg.get('sender_address', '')}"

    note = Note(content=msg.get("subject", ""))
    note["name"] = msg.get("subject", "")
    note["published"] = _ensure_datetime(msg.get("date"))

    activity = Create(actor=actor, object=note)
    activity["published"] = note["published"]
    activity["source"] = "email"
    return activity


def normalize_webex(msg: dict, room_title: str = "") -> Create:
    """Convert a Webex WebexClient message dict to an AS2 Create activity."""
    sender = msg.get("person_email", "")
    actor = Person(name=sender)
    actor["id"] = f"mailto:{sender}"

    note = Note(content=msg.get("text", "") or msg.get("markdown", "") or "")
    note["name"] = room_title
    note["published"] = _ensure_datetime(msg.get("created"))

    activity = Create(actor=actor, object=note)
    activity["published"] = note["published"]
    activity["source"] = "webex"
    return activity


def activity_to_dict(activity: Create) -> dict:
    """Serialize an AS2 activity to a plain dict."""
    return json.loads(str(activity))


def sort_key(activity: Create) -> datetime:
    """Return the published datetime for sorting (newest first)."""
    return activity["published"]
