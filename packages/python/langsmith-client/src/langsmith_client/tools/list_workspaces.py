#!/usr/bin/env python3
"""
List LangSmith workspaces available to the current API key.

This tool queries the LangSmith API to retrieve workspace information
and displays it in a formatted table or JSON output.

PREREQUISITES:
- LANGSMITH_API_KEY: Your LangSmith API key

USAGE:
    langsmith-workspaces list
    langsmith-workspaces list --format json
    langsmith-workspaces list --format table

API REFERENCE:
    https://api.smith.langchain.com/api/v1/workspaces
"""

import json
from datetime import datetime

import click
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env file
load_dotenv()

# LangSmith API base URL
LANGSMITH_API_URL = "https://api.smith.langchain.com"

HTTP_OK = 200

_REQUEST_TIMEOUT = 30


# =============================================================================
# Pydantic Models (Result Objects)
# =============================================================================


class Workspace(BaseModel):
    """A LangSmith workspace with its metadata and permissions."""

    id: str
    display_name: str
    organization_id: str
    role_name: str
    role_id: str
    is_personal: bool
    is_deleted: bool = False
    read_only: bool = False
    created_at: str
    tenant_handle: str | None = None
    permissions: list[str] = Field(default_factory=list)

    @property
    def created_date(self) -> str:
        """Return formatted creation date."""
        try:
            dt = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            return self.created_at[:10] if self.created_at else "N/A"


class WorkspacesResult(BaseModel):
    """Result container for workspace queries."""

    workspaces: list[Workspace]
    count: int

    @classmethod
    def from_api_response(cls, data: list[dict]) -> "WorkspacesResult":
        """Create a WorkspacesResult from the raw API response."""
        workspaces = [Workspace.model_validate(w) for w in data]
        return cls(workspaces=workspaces, count=len(workspaces))

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump()

    def filter_by_role(self, role_name: str) -> "WorkspacesResult":
        """Return a new result with only workspaces matching the role."""
        filtered = [
            w for w in self.workspaces if role_name.lower() in w.role_name.lower()
        ]
        return WorkspacesResult(workspaces=filtered, count=len(filtered))

    def filter_active(self) -> "WorkspacesResult":
        """Return a new result with only non-deleted workspaces."""
        filtered = [w for w in self.workspaces if not w.is_deleted]
        return WorkspacesResult(workspaces=filtered, count=len(filtered))


# =============================================================================
# API Client
# =============================================================================


def get_workspaces(api_key: str) -> WorkspacesResult:
    """
    Query LangSmith API for available workspaces.

    Args:
        api_key: LangSmith API key

    Returns:
        WorkspacesResult containing all accessible workspaces

    Raises:
        RuntimeError: If the API request fails
    """
    response = requests.get(
        f"{LANGSMITH_API_URL}/api/v1/workspaces",
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
        },
        timeout=_REQUEST_TIMEOUT,
    )

    if response.status_code == HTTP_OK:
        return WorkspacesResult.from_api_response(response.json())
    else:
        raise RuntimeError(
            f"Failed to fetch workspaces: {response.status_code}\n{response.text}"
        )


# =============================================================================
# CLI Output Formatters
# =============================================================================


def print_table(result: WorkspacesResult) -> None:
    """Print workspaces as a formatted table."""
    if not result.workspaces:
        click.echo("No workspaces found.")
        return

    # Calculate column widths
    name_width = max(len(w.display_name) for w in result.workspaces)
    name_width = max(name_width, len("Display Name"))
    role_width = max(len(w.role_name) for w in result.workspaces)
    role_width = max(role_width, len("Role"))

    # Header
    click.echo(f"\nFound {result.count} workspace(s):\n")
    header = (
        f"{'Display Name':<{name_width}}  {'ID':<36}  "
        f"{'Role':<{role_width}}  {'Created'}"
    )
    click.echo(header)
    click.echo("-" * len(header))

    # Rows
    for w in result.workspaces:
        row = (
            f"{w.display_name:<{name_width}}  {w.id:<36}  "
            f"{w.role_name:<{role_width}}  {w.created_date}"
        )
        click.echo(row)

    click.echo()


def print_json(result: WorkspacesResult) -> None:
    """Print workspaces as JSON."""
    click.echo(json.dumps(result.to_dict(), indent=2, default=str))


# =============================================================================
# CLI Commands
# =============================================================================


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Query LangSmith workspaces.

    \b
    PREREQUISITES:
    - LANGSMITH_API_KEY: Your LangSmith API key (set in .env or environment)
    """
    pass


@cli.command("list")
@click.option(
    "--api-key",
    envvar="LANGSMITH_API_KEY",
    help="LangSmith API key (defaults to LANGSMITH_API_KEY env var)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table)",
)
@click.option(
    "--role",
    "role_filter",
    help="Filter by role name (contains match)",
)
@click.option(
    "--active-only",
    is_flag=True,
    help="Show only non-deleted workspaces",
)
def list_workspaces(
    api_key: str | None,
    output_format: str,
    role_filter: str | None,
    active_only: bool,
):
    """List available LangSmith workspaces."""
    if not api_key:
        raise click.ClickException(
            "LANGSMITH_API_KEY is required. "
            "Set it as an environment variable or use --api-key."
        )

    try:
        result = get_workspaces(api_key)

        # Apply filters
        if active_only:
            result = result.filter_active()
        if role_filter:
            result = result.filter_by_role(role_filter)

        # Output
        if output_format == "json":
            print_json(result)
        else:
            print_table(result)

    except RuntimeError as e:
        raise click.ClickException(str(e)) from e


@cli.command("get")
@click.option(
    "--api-key",
    envvar="LANGSMITH_API_KEY",
    help="LangSmith API key",
)
@click.argument("workspace_id")
def get_workspace(api_key: str | None, workspace_id: str):
    """Get details for a specific workspace by ID."""
    if not api_key:
        raise click.ClickException(
            "LANGSMITH_API_KEY is required. "
            "Set it as an environment variable or use --api-key."
        )

    try:
        result = get_workspaces(api_key)
        workspace = next((w for w in result.workspaces if w.id == workspace_id), None)

        if workspace:
            click.echo(json.dumps(workspace.model_dump(), indent=2, default=str))
        else:
            raise click.ClickException(f"Workspace not found: {workspace_id}")

    except RuntimeError as e:
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    cli()
