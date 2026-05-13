"""Click CLI for the unified messages inbox."""

from __future__ import annotations

import json
import logging

import click
from ess_outlook.graph import GraphClient
from ess_webex.auth import get_access_token
from ess_webex.client import WebexClient

from .aggregator import MessageAggregator
from .normalize import activity_to_dict

logger = logging.getLogger(__name__)


def _try_outlook() -> GraphClient | None:
    """Attempt to initialize the Outlook client."""
    try:
        return GraphClient()
    except Exception:
        logger.debug("Outlook client unavailable", exc_info=True)
        return None


def _try_webex() -> WebexClient | None:
    """Attempt to initialize the Webex client."""
    try:
        return WebexClient(access_token=get_access_token())
    except Exception:
        logger.debug("Webex client unavailable", exc_info=True)
        return None


def _get_aggregator() -> MessageAggregator:
    """Build a MessageAggregator from available clients."""
    outlook_client = _try_outlook()
    webex_client = _try_webex()

    if not outlook_client and not webex_client:
        msg = (
            "No message sources available. "
            "Configure Outlook (CLIENT_ID/TENANT_ID) "
            "and/or Webex (WEBEX_ACCESS_TOKEN or 'ess-webex login')."
        )
        raise click.ClickException(msg)

    return MessageAggregator(outlook_client=outlook_client, webex_client=webex_client)


def _format_row(activity) -> str:
    """Format a single AS2 activity as a multi-line block."""
    src = activity["source"][0].upper()

    actor = activity["actor"]
    sender = actor["name"] if "name" in actor else str(actor)

    published = activity["published"]
    if hasattr(published, "strftime"):
        published = published.strftime("%Y-%m-%d %H:%M")

    obj = activity["object"]
    summary = obj["name"] if "name" in obj else ""
    summary = summary or ""

    content = obj["content"] if "content" in obj else ""
    content = (content or "").replace("\n", " ").strip()
    if len(content) > 80:  # noqa: PLR2004 -- preview length
        content = content[:77] + "..."

    header = f"[{src}] {sender}  {published}"
    if summary:
        header += f"  ({summary})"
    return f"{header}\n     {content}"


@click.command()
@click.option("--limit", default=25, show_default=True, help="Max messages")
@click.option("--email-only", is_flag=True, help="Only email.")
@click.option("--webex-only", is_flag=True, help="Only Webex.")
@click.option("--webex-rooms", help="Comma-separated Webex room IDs.")
@click.option("--json-output", is_flag=True, help="Emit AS2 JSON.")
def cli(
    limit: int,
    email_only: bool,
    webex_only: bool,
    webex_rooms: str | None,
    json_output: bool,
) -> None:
    """Show recent messages from email and Webex, sorted by date."""
    aggregator = _get_aggregator()
    room_ids = [r.strip() for r in webex_rooms.split(",")] if webex_rooms else None

    try:
        activities = aggregator.get_latest(
            limit=limit,
            email_only=email_only,
            webex_only=webex_only,
            webex_room_ids=room_ids,
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    if json_output:
        click.echo(json.dumps([activity_to_dict(a) for a in activities], indent=2))
        return

    if not activities:
        click.echo("No messages found.")
        return

    for i, activity in enumerate(activities):
        if i > 0:
            click.echo()
        click.echo(_format_row(activity))
