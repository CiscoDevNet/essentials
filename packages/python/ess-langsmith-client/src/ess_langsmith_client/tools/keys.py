#!/usr/bin/env python3
"""
Manage LangSmith API keys -- list, create, and delete.

PREREQUISITES:
- LANGSMITH_API_KEY: A valid LangSmith API key with admin access

USAGE:
    langsmith-client keys list
    langsmith-client keys list --expired
    langsmith-client keys list --older-than 90
    langsmith-client keys create "LangSmith Deployment: my-app"
    langsmith-client keys delete "my-old-key" "another-old-key"
    langsmith-client keys delete "duplicated-name" --all
"""

import json
import os
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

import click
import requests
from dotenv import load_dotenv

from ess_langsmith_client.client import _REQUEST_TIMEOUT, _SMITH_API_URL

load_dotenv()


# =============================================================================
# Client
# =============================================================================


class APIKeyClient:
    """Client for the LangSmith API key management endpoints."""

    def __init__(
        self,
        api_key: str | None = None,
        workspace_id: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("LANGSMITH_API_KEY")
        if not self.api_key:
            raise ValueError(
                "LANGSMITH_API_KEY is required. "
                "Set it as an environment variable or pass --api-key."
            )
        self.headers: dict[str, str] = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        workspace_id = workspace_id or os.environ.get("LANGSMITH_WORKSPACE_ID")
        if workspace_id:
            self.headers["X-Tenant-Id"] = workspace_id

    def list_keys(self) -> list[dict[str, Any]]:
        """List all API keys for the current tenant."""
        resp = requests.get(
            f"{_SMITH_API_URL}/api/v1/api-key",
            headers=self.headers,
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f"Failed to list API keys: {resp.status_code}\n{resp.text}"
            )
        return resp.json()

    def create_key(self, description: str) -> dict[str, Any]:
        """Create a new service API key.

        Returns the full key metadata including the raw key value, which is
        only available at creation time.
        """
        resp = requests.post(
            f"{_SMITH_API_URL}/api/v1/api-key",
            headers=self.headers,
            json={"description": description},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f"Failed to create API key: {resp.status_code}\n{resp.text}"
            )
        return resp.json()

    def delete_key(self, key_id: str) -> dict[str, Any]:
        """Delete an API key by its UUID."""
        resp = requests.delete(
            f"{_SMITH_API_URL}/api/v1/api-key/{key_id}",
            headers=self.headers,
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f"Failed to delete key {key_id}: {resp.status_code}\n{resp.text}"
            )
        return resp.json()


# =============================================================================
# Output formatters
# =============================================================================


def _parse_dt(value: str | datetime) -> datetime:
    """Parse API timestamps; normalize RFC3339 Z and naive datetimes to UTC."""
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _age_days(key: dict[str, Any]) -> int | None:
    """Return the number of days since the key was created, or None."""
    created_at = key.get("created_at")
    if not created_at:
        return None
    created_at = _parse_dt(created_at)
    return (datetime.now(timezone.utc) - created_at).days


def _is_expired(key: dict[str, Any]) -> bool:
    expires_at = key.get("expires_at")
    if not expires_at:
        return False
    expires_at = _parse_dt(expires_at)
    return expires_at < datetime.now(timezone.utc)


def _format_expires(key: dict[str, Any]) -> str:
    expires_at = key.get("expires_at")
    if not expires_at:
        return "never"
    expires_at = _parse_dt(expires_at)
    label = expires_at.strftime("%Y-%m-%d")
    if _is_expired(key):
        return f"{label} (EXPIRED)"
    return label


def _print_table(keys: list[dict[str, Any]]) -> None:
    if not keys:
        click.echo("No API keys found.")
        return

    desc_w = max((len(k.get("description", "")) for k in keys), default=20)
    desc_w = max(desc_w, 11)

    header = (
        f"{'Description':<{desc_w}}  {'Short Key':<12}  "
        f"{'Age (days)':<10}  {'Expires':<22}  ID"
    )
    click.echo(f"\nFound {len(keys)} key(s):\n")
    click.echo(header)
    click.echo("-" * len(header))

    for k in keys:
        age = _age_days(k)
        age_str = str(age) if age is not None else "?"
        expires = _format_expires(k)
        click.echo(
            f"{k.get('description', ''):<{desc_w}}  "
            f"{k.get('short_key', ''):<12}  "
            f"{age_str:<10}  "
            f"{expires:<22}  "
            f"{k.get('id', '')}"
        )
    click.echo()


# =============================================================================
# CLI
# =============================================================================


def _select_targets(
    all_keys: list[dict[str, Any]],
    descriptions: tuple[str, ...],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Return (targets, duplicates_by_description).

    duplicates_by_description holds only descriptions matching >1 key.
    """
    keys_by_description: dict[str, list[dict[str, Any]]] = {}
    for key in all_keys:
        description = key.get("description")
        if description in descriptions:
            keys_by_description.setdefault(description, []).append(key)
    targets = [
        key for matching_keys in keys_by_description.values() for key in matching_keys
    ]
    duplicates = {
        description: matching_keys
        for description, matching_keys in keys_by_description.items()
        if len(matching_keys) > 1
    }
    return targets, duplicates


def _format_duplicate_error(duplicates: dict[str, list[dict[str, Any]]]) -> str:
    """Build the error message listing descriptions that match multiple keys."""
    error_lines = ["Refusing to delete: these descriptions match multiple keys."]
    for description, matching_keys in sorted(duplicates.items()):
        error_lines.append(f"  '{description}' matches {len(matching_keys)} keys:")
        error_lines.extend(
            f"      {key.get('short_key', '???')}  id={key.get('id', '???')}  "
            f"expires: {_format_expires(key)}"
            for key in matching_keys
        )
    error_lines.append("Re-run with --all to delete every matching key.")
    return "\n".join(error_lines)


def _common_options(func):
    func = click.option(
        "--api-key",
        envvar="LANGSMITH_API_KEY",
        help="LangSmith API key (defaults to LANGSMITH_API_KEY env var)",
    )(func)
    func = click.option(
        "--workspace-id",
        envvar="LANGSMITH_WORKSPACE_ID",
        help="Target workspace ID (required for PATs with multiple workspaces)",
    )(func)
    return func


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Manage LangSmith API keys.

    \b
    PREREQUISITES:
    - LANGSMITH_API_KEY: A valid API key with admin access
    """


@cli.command("list")
@_common_options
@click.option("--expired", is_flag=True, help="Show only expired keys")
@click.option(
    "--older-than",
    type=int,
    default=None,
    help="Show only keys older than N days (based on created_at)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table)",
)
def list_keys(
    api_key: str | None,
    workspace_id: str | None,
    expired: bool,
    older_than: int | None,
    output_format: str,
):
    """List API keys."""
    try:
        client = APIKeyClient(api_key, workspace_id)
        keys = client.list_keys()
    except (ValueError, RuntimeError) as e:
        raise click.ClickException(str(e)) from e

    if expired:
        keys = [k for k in keys if _is_expired(k)]

    if older_than is not None:
        keys = [k for k in keys if (_age_days(k) or 0) > older_than]

    if output_format == "json":
        click.echo(json.dumps(keys, indent=2, default=str))
    else:
        _print_table(keys)


@cli.command()
@_common_options
@click.argument("description")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table)",
)
def create(
    api_key: str | None,
    workspace_id: str | None,
    description: str,
    output_format: str,
):
    """Create a new service API key.

    The full key value is shown only once -- copy it immediately.

    \b
    Examples:
        langsmith-client keys create "LangSmith Deployment: hello-world-graph"
        langsmith-client keys create "my-service-key" --format json
    """
    try:
        client = APIKeyClient(api_key, workspace_id)
        result = client.create_key(description)
    except (ValueError, RuntimeError) as e:
        raise click.ClickException(str(e)) from e

    if output_format == "json":
        click.echo(json.dumps(result, indent=2, default=str))
    else:
        click.echo()
        click.echo(click.style("Key created successfully.", fg="green"))
        click.echo()
        click.echo(f"  Description:  {result.get('description', '')}")
        click.echo(f"  ID:           {result.get('id', '')}")
        click.echo(f"  Short Key:    {result.get('short_key', '')}")
        click.echo()
        click.echo(
            click.style(
                "  COPY THIS NOW -- the full key is only shown once:",
                fg="yellow",
                bold=True,
            )
        )
        click.echo(f"  {result.get('key', '???')}")
        click.echo()


@cli.command()
@_common_options
@click.argument("descriptions", nargs=-1, required=True)
@click.option(
    "--all",
    "delete_all",
    is_flag=True,
    help=(
        "Delete every key matching a description, even when a description "
        "matches more than one key (default: error on duplicates)."
    ),
)
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
def delete(
    api_key: str | None,
    workspace_id: str | None,
    descriptions: tuple[str, ...],
    delete_all: bool,
    yes: bool,
):
    """Delete API keys by description (name).

    Pass one or more key descriptions as arguments. The tool matches them
    exactly against the description field shown in the LangSmith UI.

    By default, if any description matches more than one key the command
    refuses to delete and exits with an error. Pass --all to explicitly
    delete every matching key.

    \b
    Examples:
        langsmith-client keys delete "my-old-key"
        langsmith-client keys delete "key-1" "key-2" "key-3"
        langsmith-client keys delete "key-1" --yes
        langsmith-client keys delete "duplicated-name" --all
    """
    try:
        client = APIKeyClient(api_key, workspace_id)
        all_keys = client.list_keys()
    except (ValueError, RuntimeError) as e:
        raise click.ClickException(str(e)) from e

    targets, duplicates = _select_targets(all_keys, descriptions)

    if duplicates and not delete_all:
        raise click.ClickException(_format_duplicate_error(duplicates))

    if not targets:
        matched_descs = {k.get("description") for k in all_keys}
        labels = sorted(d or "(no description)" for d in matched_descs)
        click.echo("No keys found matching the given descriptions.")
        click.echo(f"Available descriptions: {', '.join(labels)}")
        return

    click.echo(f"\nKeys to delete ({len(targets)}):\n")
    for k in targets:
        expires = _format_expires(k)
        click.echo(
            f"  {k['description']}  ({k.get('short_key', '???')})  expires: {expires}"
        )
    click.echo()

    if not yes:
        click.confirm("Delete these keys?", abort=True)

    deleted = 0
    failed = 0
    for k in targets:
        desc = k.get("description", k["id"])
        try:
            client.delete_key(k["id"])
            click.echo(click.style(f"  Deleted: {desc}", fg="green"))
            deleted += 1
        except RuntimeError as e:
            click.echo(click.style(f"  Failed:  {desc} -- {e}", fg="red"))
            failed += 1

    click.echo()
    if deleted:
        click.echo(click.style(f"{deleted} key(s) deleted.", fg="green"))
    if failed:
        click.echo(click.style(f"{failed} key(s) failed.", fg="red"))


if __name__ == "__main__":
    cli()
