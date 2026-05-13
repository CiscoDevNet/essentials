"""Click CLI for Webex."""

from __future__ import annotations

import json

import click

from ess_webex.auth import WebexOAuthError, get_access_token, login
from ess_webex.client import WebexClient


def _get_client(ctx: click.Context) -> WebexClient:
    """Lazily create and cache the WebexClient on the context."""
    if "client" not in ctx.obj:
        try:
            token = get_access_token()
        except WebexOAuthError as exc:
            raise click.ClickException(str(exc)) from exc
        ctx.obj["client"] = WebexClient(access_token=token)
    return ctx.obj["client"]


def _handle_error(exc: Exception) -> None:
    """Convert any backend exception into a ClickException."""
    raise click.ClickException(str(exc)) from exc


def _echo_table(rows: list[dict], columns: list[tuple[str, str, int]]) -> None:
    """Print a formatted table from a list of dicts.

    *columns* is a list of (dict_key, header_label, width) tuples.
    """
    header = "".join(f"{label:<{width}}" for _, label, width in columns)
    click.echo(header)
    click.echo("-" * len(header))
    for row in rows:
        parts = []
        for key, _, width in columns:
            val = str(row.get(key) or "")
            if len(val) > width - 2:
                val = val[: width - 5] + "..."
            parts.append(f"{val:<{width}}")
        click.echo("".join(parts))


def _echo_detail(data: dict) -> None:
    """Print key-value pairs for a single item."""
    max_key = max(len(k) for k in data)
    for key, val in data.items():
        click.echo(f"{key:<{max_key + 2}} {val}")


# -- Main group --


@click.group()
@click.option("--json-output", "json_output", is_flag=True, help="Emit JSON output.")
@click.pass_context
def cli(ctx: click.Context, json_output: bool) -> None:
    """Interact with Webex rooms, messages, teams, and meetings."""
    ctx.ensure_object(dict)
    ctx.obj["json_output"] = json_output


# -- Login --


@cli.command("login")
def login_cmd() -> None:
    """Authenticate with Webex via OAuth (opens browser)."""
    try:
        login()
        click.echo("Login successful. Token cached.")
    except WebexOAuthError as exc:
        raise click.ClickException(str(exc)) from exc


# -- Rooms --


@cli.command("rooms")
@click.argument("room_id", required=False)
@click.option("--max", "max_results", default=25, show_default=True, help="Max results")
@click.option(
    "--type",
    "type_",
    type=click.Choice(["group", "direct"]),
    help="Room type.",
)
@click.option("--team", "team_id", help="Filter by team ID.")
@click.option(
    "--sort-by",
    type=click.Choice(["lastactivity", "created"]),
    default="lastactivity",
    show_default=True,
)
@click.pass_context
def rooms(  # noqa: PLR0913 -- Click requires all params as function args
    ctx: click.Context,
    room_id: str | None,
    max_results: int,
    type_: str | None,
    team_id: str | None,
    sort_by: str,
) -> None:
    """List rooms or get room details."""
    client = _get_client(ctx)
    try:
        if room_id:
            data = client.get_room(room_id)
            if ctx.obj["json_output"]:
                click.echo(json.dumps(data, indent=2, default=str))
            else:
                _echo_detail(data)
            return

        data = client.list_rooms(
            max_results=max_results, type_=type_, team_id=team_id, sort_by=sort_by
        )
    except Exception as exc:
        _handle_error(exc)

    if ctx.obj["json_output"]:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    if not data:
        click.echo("No rooms found.")
        return

    _echo_table(
        data,
        [
            ("title", "Title", 40),
            ("type", "Type", 10),
            ("last_activity", "Last Activity", 28),
            ("id", "ID", 50),
        ],
    )


# -- Teams --


@cli.command("teams")
@click.argument("team_id", required=False)
@click.option("--max", "max_results", default=25, show_default=True, help="Max results")
@click.pass_context
def teams(ctx: click.Context, team_id: str | None, max_results: int) -> None:
    """List teams or get team details."""
    client = _get_client(ctx)
    try:
        if team_id:
            data = client.get_team(team_id)
            if ctx.obj["json_output"]:
                click.echo(json.dumps(data, indent=2, default=str))
            else:
                _echo_detail(data)
            return

        data = client.list_teams(max_results=max_results)
    except Exception as exc:
        _handle_error(exc)

    if ctx.obj["json_output"]:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    if not data:
        click.echo("No teams found.")
        return

    _echo_table(
        data,
        [
            ("name", "Name", 40),
            ("created", "Created", 28),
            ("id", "ID", 50),
        ],
    )


# -- Messages --


@cli.group("messages")
def messages() -> None:
    """Read and send Webex messages."""


@messages.command("list")
@click.argument("room_id")
@click.option("--max", "max_results", default=25, show_default=True, help="Max results")
@click.pass_context
def messages_list(ctx: click.Context, room_id: str, max_results: int) -> None:
    """List recent messages in a room."""
    client = _get_client(ctx)
    try:
        data = client.list_messages(room_id, max_results=max_results)
    except Exception as exc:
        _handle_error(exc)

    if ctx.obj["json_output"]:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    if not data:
        click.echo("No messages found.")
        return

    _echo_table(
        data,
        [("person_email", "From", 30), ("created", "Date", 28), ("text", "Text", 60)],
    )


@messages.command("read")
@click.argument("message_id")
@click.pass_context
def messages_read(ctx: click.Context, message_id: str) -> None:
    """Read a specific message."""
    client = _get_client(ctx)
    try:
        data = client.get_message(message_id)
    except Exception as exc:
        _handle_error(exc)

    if ctx.obj["json_output"]:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    click.echo(f"From:    {data['person_email']}")
    click.echo(f"Date:    {data['created']}")
    click.echo("-" * 60)
    click.echo(data.get("text") or data.get("markdown") or "")


@messages.command("send")
@click.argument("text")
@click.option("--room", "room_id", help="Room ID to send to.")
@click.option("--email", "to_person_email", help="Email for direct message.")
@click.option("--markdown", is_flag=True, help="Treat text as markdown.")
@click.pass_context
def messages_send(
    ctx: click.Context,
    text: str,
    room_id: str | None,
    to_person_email: str | None,
    markdown: bool,
) -> None:
    """Send a message to a room or person."""
    if not room_id and not to_person_email:
        raise click.UsageError("Provide --room or --email.")

    client = _get_client(ctx)
    try:
        data = client.send_message(
            text,
            room_id=room_id,
            to_person_email=to_person_email,
            markdown=text if markdown else None,
        )
    except Exception as exc:
        _handle_error(exc)

    if ctx.obj["json_output"]:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(f"Message sent (id: {data['id']})")


# -- Meetings --


@cli.group("meetings")
def meetings() -> None:
    """List and create Webex meetings."""


@meetings.command("list")
@click.option("--from", "from_", help="Start date (ISO-8601).")
@click.option("--to", "to_", help="End date (ISO-8601).")
@click.option("--max", "max_results", default=25, show_default=True, help="Max results")
@click.pass_context
def meetings_list(
    ctx: click.Context, from_: str | None, to_: str | None, max_results: int
) -> None:
    """List meetings in a date range."""
    client = _get_client(ctx)
    try:
        data = client.list_meetings(from_=from_, to_=to_, max_results=max_results)
    except Exception as exc:
        _handle_error(exc)

    if ctx.obj["json_output"]:
        click.echo(json.dumps(data, indent=2, default=str))
        return

    if not data:
        click.echo("No meetings found.")
        return

    _echo_table(
        data,
        [
            ("title", "Title", 40),
            ("start", "Start", 22),
            ("end", "End", 22),
            ("state", "State", 12),
        ],
    )


@meetings.command("get")
@click.argument("meeting_id")
@click.pass_context
def meetings_get(ctx: click.Context, meeting_id: str) -> None:
    """Get details of a meeting."""
    client = _get_client(ctx)
    try:
        data = client.get_meeting(meeting_id)
    except Exception as exc:
        _handle_error(exc)

    if ctx.obj["json_output"]:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        _echo_detail(data)


@meetings.command("create")
@click.argument("title")
@click.option("--start", required=True, help="Start datetime (ISO-8601).")
@click.option("--end", required=True, help="End datetime (ISO-8601).")
@click.option("--invitees", help="Comma-separated emails.")
@click.pass_context
def meetings_create(
    ctx: click.Context,
    title: str,
    start: str,
    end: str,
    invitees: str | None,
) -> None:
    """Create a meeting."""
    client = _get_client(ctx)
    invitee_list = [e.strip() for e in invitees.split(",")] if invitees else None
    try:
        data = client.create_meeting(title, start, end, invitees=invitee_list)
    except Exception as exc:
        _handle_error(exc)

    if ctx.obj["json_output"]:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(f"Meeting created: {data.get('title')} (id: {data['id']})")
