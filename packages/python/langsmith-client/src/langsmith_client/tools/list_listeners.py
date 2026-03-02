#!/usr/bin/env python3
"""
List LangSmith listeners (hybrid deployment agents).

Listeners connect the LangSmith control plane to a self-hosted Kubernetes
cluster. The listener ID is required when creating Docker-based deployments
against a self-hosted cluster.

PREREQUISITES:
- LANGSMITH_API_KEY: Your LangSmith API key
- LANGSMITH_WORKSPACE_ID: Your LangSmith workspace ID

USAGE:
    langsmith-listeners list
    langsmith-listeners list --format json

CONTROL PLANE API REFERENCE:
    https://docs.langchain.com/langsmith/api-ref-control-plane
"""

import json
from typing import Any

import click

from langsmith_client import (
    ControlPlaneClient,
    common_options,
    create_client,
)

# =============================================================================
# Output Formatters
# =============================================================================


def print_table(listeners: list[dict[str, Any]]) -> None:
    """Print listeners as a formatted table."""
    if not listeners:
        click.echo("No listeners found.")
        return

    id_width = max(
        (len(str(listener.get("id", ""))) for listener in listeners),
        default=36,
    )
    id_width = max(id_width, len("ID"))
    name_width = max(
        (len(str(listener.get("name", ""))) for listener in listeners),
        default=20,
    )
    name_width = max(name_width, len("Name"))

    click.echo(f"\nFound {len(listeners)} listener(s):\n")
    header = f"{'ID':<{id_width}}  {'Name':<{name_width}}  Status"
    click.echo(header)
    click.echo("-" * len(header))

    for listener in listeners:
        click.echo(
            f"{str(listener.get('id', '')):<{id_width}}  "
            f"{str(listener.get('name', '')):<{name_width}}  "
            f"{listener.get('status', 'N/A')}"
        )

    click.echo()


def print_json(listeners: list[dict[str, Any]]) -> None:
    """Print listeners as JSON."""
    click.echo(json.dumps(listeners, indent=2, default=str))


# =============================================================================
# CLI Commands
# =============================================================================


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """List LangSmith listeners for hybrid (self-hosted) deployments.

    \b
    PREREQUISITES:
    - LANGSMITH_API_KEY: Your LangSmith API key
    - LANGSMITH_WORKSPACE_ID: Your workspace ID (from LangSmith settings)

    \b
    The listener ID displayed here is used as --listener-id when creating
    Docker-based deployments against a self-hosted Kubernetes cluster.
    """
    pass


@cli.command("list")
@common_options
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table)",
)
def list_listeners(
    region: str,
    api_key: str | None,
    workspace_id: str | None,
    output_format: str,
):
    """List listeners for hybrid deployments."""
    client: ControlPlaneClient = create_client(
        ControlPlaneClient, api_key, workspace_id, region
    )

    click.echo("Fetching listeners...")

    try:
        result = client.list_listeners()
        listeners = (
            result.get("resources", result) if isinstance(result, dict) else result
        )

        if output_format == "json":
            print_json(listeners)
        else:
            print_table(listeners)

    except RuntimeError as e:
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    cli()
