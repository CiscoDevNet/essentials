#!/usr/bin/env python3
"""
List and delete LangSmith listeners (hybrid deployment agents).

Listeners connect the LangSmith control plane to a self-hosted Kubernetes
cluster. The listener ID is required when creating Docker-based deployments
against a self-hosted cluster.

PREREQUISITES:
- LANGSMITH_API_KEY: Your LangSmith API key
- LANGSMITH_WORKSPACE_ID: Your LangSmith workspace ID

USAGE:
    langsmith-client listeners list
    langsmith-client listeners list --format json
    langsmith-client listeners delete <listener-id> --dry-run
    langsmith-client listeners delete <listener-id>

CONTROL PLANE API REFERENCE:
    https://docs.langchain.com/langsmith/api-ref-control-plane
"""

import json
import sys
from typing import Any

import click

from ess_langsmith_client import (
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
    compute_width = max(
        (len(str(listener.get("compute_id", ""))) for listener in listeners),
        default=20,
    )
    compute_width = max(compute_width, len("Compute ID"))

    click.echo(f"\nFound {len(listeners)} listener(s):\n")
    header = f"{'ID':<{id_width}}  {'Compute ID':<{compute_width}}  Version"
    click.echo(header)
    click.echo("-" * len(header))

    for listener in listeners:
        click.echo(
            f"{str(listener.get('id', '')):<{id_width}}  "
            f"{str(listener.get('compute_id', '')):<{compute_width}}  "
            f"{listener.get('version') or 'N/A'}"
        )

    click.echo()


def print_json(listeners: list[dict[str, Any]]) -> None:
    """Print listeners as JSON."""
    click.echo(json.dumps(listeners, indent=2, default=str))


def _describe_listener(listener: dict[str, Any]) -> str:
    namespaces = (listener.get("compute_config") or {}).get("k8s_namespaces") or []
    return (
        f"{listener.get('id', '')}  "
        f"compute_id={listener.get('compute_id') or '?'}  "
        f"namespaces={','.join(namespaces) or '?'}  "
        f"created={str(listener.get('created_at') or '?')[:10]}"
    )


def _format_in_use_error(placements: dict[str, list[dict[str, Any]]]) -> str:
    """Build the error listing deployments still placed on target listeners."""
    lines = ["Refusing to delete: these listeners still have deployments."]
    for listener_id, deployments in sorted(placements.items()):
        lines.append(f"  {listener_id} serves {len(deployments)} deployment(s):")
        lines.extend(
            f"      {deployment.get('name', '?')}  id={deployment.get('id', '?')}"
            for deployment in deployments
        )
    lines.append("Delete or move those deployments first.")
    return "\n".join(lines)


# =============================================================================
# Helpers
# =============================================================================


def _deployments_by_listener(
    deployments: list[dict[str, Any]], listener_ids: tuple[str, ...]
) -> dict[str, list[dict[str, Any]]]:
    """Map each target listener ID to the deployments placed on it."""
    placements: dict[str, list[dict[str, Any]]] = {}
    for deployment in deployments:
        listener_id = (deployment.get("source_config") or {}).get("listener_id")
        if listener_id in listener_ids:
            placements.setdefault(listener_id, []).append(deployment)
    return placements


def _resolve_targets(
    client: ControlPlaneClient, listener_ids: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Look up each listener and dedupe by the ID the API returns.

    Placement checks and deletes must use that ID. An argument the server
    resolves to a different ID (for example a non-canonical UUID spelling)
    would otherwise miss deployments placed on the real listener.
    """
    targets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for listener_id in dict.fromkeys(listener_ids):
        listener = client.get_listener(listener_id)
        resolved_id = listener.get("id")
        if not isinstance(resolved_id, str) or not resolved_id:
            raise RuntimeError(
                f"Listener lookup for {listener_id} did not return an id."
            )
        if resolved_id in seen:
            continue
        seen.add(resolved_id)
        targets.append(listener)
    return targets


def _refuse_in_use(client: ControlPlaneClient, listener_ids: tuple[str, ...]) -> None:
    """Raise when any target listener still has deployments placed on it."""
    try:
        placements = _deployments_by_listener(
            client.list_all_deployments(), listener_ids
        )
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    if placements:
        raise click.ClickException(_format_in_use_error(placements))


def _is_interactive() -> bool:
    return sys.stdin.isatty()


def _confirm_or_abort(count: int, workspace_id: str | None, *, skip: bool) -> None:
    """Require explicit consent before deleting listeners."""
    if skip:
        return
    if not _is_interactive():
        raise click.UsageError(
            "No terminal to confirm the delete; pass --yes to confirm it."
        )
    click.confirm(
        f"Delete {count} listener(s) from workspace {workspace_id or '(default)'}?",
        abort=True,
        err=True,
    )


# =============================================================================
# CLI Commands
# =============================================================================


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """List and delete LangSmith listeners for hybrid (self-hosted) deployments.

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


@cli.command("delete")
@common_options
@click.argument("listener_ids", nargs=-1, required=True)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show the listeners that would be deleted without deleting them.",
)
@click.option(
    "--yes", "-y", is_flag=True, default=False, help="Skip the confirmation prompt."
)
def delete_listeners(  # noqa: PLR0913  # one param per CLI option
    region: str,
    api_key: str | None,
    workspace_id: str | None,
    listener_ids: tuple[str, ...],
    dry_run: bool,
    yes: bool,
):
    """Delete listeners by ID.

    Refuses to delete a listener that still has deployments placed on it, so
    a live cluster cannot be detached by mistake. That check runs before the
    confirmation prompt and again immediately after it. The control plane
    DELETE has no in-use precondition, so a deployment placed after the
    second check can still be removed with the listener. Delete or move
    deployments first.

    \b
    Examples:
        langsmith-client listeners delete <listener-id> --dry-run
        langsmith-client listeners delete <listener-id>
        langsmith-client listeners delete <id-1> <id-2> --yes
    """
    client: ControlPlaneClient = create_client(
        ControlPlaneClient, api_key, workspace_id, region
    )

    try:
        targets = _resolve_targets(client, listener_ids)
    except (RuntimeError, ValueError) as e:
        raise click.ClickException(str(e)) from e

    resolved_ids = tuple(str(listener["id"]) for listener in targets)
    _refuse_in_use(client, resolved_ids)

    workspace_label = client.workspace_id or "(default)"
    click.echo(
        f"\nListeners to delete ({len(targets)}) in workspace {workspace_label}:\n"
    )
    for listener in targets:
        click.echo(f"  {_describe_listener(listener)}")
    click.echo()

    if dry_run:
        click.echo("Dry run: no listeners deleted.")
        return

    _confirm_or_abort(len(targets), client.workspace_id, skip=yes)
    _refuse_in_use(client, resolved_ids)

    deleted = 0
    failed = 0
    for listener_id in resolved_ids:
        try:
            client.delete_listener(listener_id)
            click.echo(click.style(f"  Deleted: {listener_id}", fg="green"))
            deleted += 1
        except RuntimeError as e:
            click.echo(click.style(f"  Failed:  {listener_id} -- {e}", fg="red"))
            failed += 1

    click.echo()
    if deleted:
        click.echo(click.style(f"{deleted} listener(s) deleted.", fg="green"))
    if failed:
        raise click.ClickException(f"{failed} listener(s) failed to delete.")


if __name__ == "__main__":
    cli()
