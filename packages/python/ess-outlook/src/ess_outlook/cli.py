"""Click CLI for Outlook email management."""

from __future__ import annotations

import json

import click

from ess_outlook.graph import GraphClient


def _handle_error(exc: Exception) -> None:
    """Convert any backend exception into a ClickException."""
    raise click.ClickException(str(exc)) from exc


@click.group()
@click.option("--json-output", "json_output", is_flag=True, help="Emit JSON output.")
@click.pass_context
def cli(ctx: click.Context, json_output: bool) -> None:
    """Read and manage Microsoft Outlook emails from the command line."""
    ctx.ensure_object(dict)
    ctx.obj["json_output"] = json_output
    ctx.obj["client"] = GraphClient()


@cli.command("list")
@click.option("--limit", default=25, show_default=True, help="Max messages to show.")
@click.option("--unread-only", is_flag=True, help="Only show unread messages.")
@click.option("--folder", default="inbox", show_default=True, help="Mail folder name.")
@click.pass_context
def list_messages(
    ctx: click.Context,
    limit: int,
    unread_only: bool,
    folder: str,
) -> None:
    """List recent inbox messages."""
    client = ctx.obj["client"]
    try:
        messages = client.list_messages(
            folder=folder, limit=limit, unread_only=unread_only
        )
    except Exception as exc:
        _handle_error(exc)

    if ctx.obj["json_output"]:
        click.echo(json.dumps(messages, indent=2, default=str))
        return

    if not messages:
        click.echo("No messages found.")
        return

    click.echo(f"{'ID':<10} {'Status':<8} {'Sender':<30} {'Date':<22} {'Subject'}")
    click.echo("-" * 100)

    for msg in messages:
        status = " " if msg["is_read"] else "*"
        sender = msg["sender_name"] or msg["sender_address"]
        if len(sender) > 28:  # noqa: PLR2004 -- column width for table display
            sender = sender[:25] + "..."
        subject = msg["subject"]
        if len(subject) > 40:  # noqa: PLR2004 -- column width for table display
            subject = subject[:37] + "..."

        # Truncate long IDs (Graph API IDs are very long opaque strings)
        display_id = str(msg["id"])
        if len(display_id) > 8:  # noqa: PLR2004 -- column width for table display
            display_id = display_id[:8] + ".."

        display_date = str(msg["date"])
        click.echo(
            f"{display_id:<10} {status:<8} {sender:<30} {display_date:<22} {subject}"
        )


@cli.command()
@click.argument("message_id")
@click.pass_context
def read(ctx: click.Context, message_id: str) -> None:
    """Read a specific message by ID."""
    client = ctx.obj["client"]
    try:
        msg = client.get_message(message_id)
    except Exception as exc:
        _handle_error(exc)

    if ctx.obj["json_output"]:
        click.echo(json.dumps(msg, indent=2, default=str))
        return

    click.echo(f"From:    {msg['sender_name']} <{msg['sender_address']}>")
    click.echo(f"Date:    {msg['date']}")
    click.echo(f"Subject: {msg['subject']}")
    click.echo(f"Status:  {'Read' if msg['is_read'] else 'Unread'}")
    click.echo("-" * 60)
    click.echo(msg.get("body", ""))


@cli.command("mark-read")
@click.argument("message_id", required=False)
@click.option("--all", "mark_all", is_flag=True, help="Mark all messages as read.")
@click.option("--folder", default="inbox", show_default=True, help="Mail folder name.")
@click.pass_context
def mark_read(
    ctx: click.Context,
    message_id: str | None,
    mark_all: bool,
    folder: str,
) -> None:
    """Mark a message (or all messages) as read."""
    client = ctx.obj["client"]

    if not message_id and not mark_all:
        raise click.UsageError("Provide a MESSAGE_ID or use --all.")

    try:
        if mark_all:
            count = client.mark_all_as_read(folder=folder)
            click.echo(f"Marked {count} message(s) as read.")
        else:
            client.mark_as_read(message_id)
            click.echo(f"Message {message_id} marked as read.")
    except Exception as exc:
        _handle_error(exc)


@cli.command()
@click.argument("message_id")
@click.option("--force", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def delete(ctx: click.Context, message_id: str, force: bool) -> None:
    """Delete a message by ID."""
    client = ctx.obj["client"]

    if not force:
        click.confirm(f"Delete message {message_id}? This cannot be undone", abort=True)

    try:
        client.delete_message(message_id)
        click.echo(f"Message {message_id} deleted.")
    except Exception as exc:
        _handle_error(exc)
