#!/usr/bin/env python3
"""
Manage LangSmith tracing projects.

Tracing projects (also called sessions) are created automatically when LangGraph
deployments are created. Use this tool to list and delete them.

The delete command transparently handles orphaned projects — where the linked
deployment no longer exists — by clearing the stale reference and retrying.

PREREQUISITES:
- LANGSMITH_API_KEY: Your LangSmith API key

USAGE:
    langsmith-client projects list
    langsmith-client projects list --name hello-agent-auth
    langsmith-client projects list --prefix hello-agent-dev
    langsmith-client projects info --name hello-agent-dev
    langsmith-client projects delete --id <uuid>
    langsmith-client projects delete --name hello-agent-auth
    langsmith-client projects delete --name hello-world --force
"""

import json
import os
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


class TracingProjectClient:
    """Client for the LangSmith tracing projects (sessions) API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("LANGSMITH_API_KEY")
        if not self.api_key:
            raise ValueError(
                "LANGSMITH_API_KEY is required. "
                "Set it as an environment variable or pass --api-key."
            )
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def list_projects(
        self,
        name: str | None = None,
        *,
        include_stats: bool = False,
    ) -> list[dict[str, Any]]:
        """List tracing projects, optionally filtered by exact name.

        Args:
            name: Filter by exact project name.
            include_stats: Include aggregate stats (run_count, latency, etc.).
        """
        params: dict[str, str] = {}
        if name:
            params["name"] = name
        if include_stats:
            params["include_stats"] = "true"
        resp = requests.get(
            f"{_SMITH_API_URL}/api/v1/sessions",
            headers=self.headers,
            params=params,
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f"Failed to list projects: {resp.status_code}\n{resp.text}"
            )
        return resp.json()

    def list_projects_by_prefix(
        self,
        prefix: str,
        *,
        include_stats: bool = False,
    ) -> list[dict[str, Any]]:
        """List tracing projects belonging to a canonical name base.

        Anchored match: a project's name equals ``prefix`` or starts with
        ``prefix + "-"``. This finds the live tracing project for a service
        regardless of any git-SHA rescue suffix (e.g. ``hello-agent-dev`` and
        ``hello-agent-dev-3f9a2c`` both match, but ``hello-agent-prod`` does
        not).
        """
        projects = self.list_projects(include_stats=include_stats)
        anchor = f"{prefix}-"
        return [
            project
            for project in projects
            if project.get("name") == prefix
            or str(project.get("name", "")).startswith(anchor)
        ]

    def get_project(self, name: str) -> dict[str, Any] | None:
        """Get a single project by exact name, with stats.

        Returns:
            Project dict with stats fields (run_count, last_run_start_time, etc.),
            or None if no project matches.
        """
        projects = self.list_projects(name=name, include_stats=True)
        return projects[0] if projects else None

    def get_project_by_id(self, project_id: str) -> dict[str, Any] | None:
        """Get a single project by ID, with stats.

        Returns:
            Project dict with stats fields (run_count, last_run_start_time, etc.),
            or None if no project matches the ID.
        """
        resp = requests.get(
            f"{_SMITH_API_URL}/api/v1/sessions/{project_id}",
            headers=self.headers,
            params={"include_stats": "true"},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code == HTTPStatus.NOT_FOUND:
            return None
        if resp.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f"Failed to get project {project_id}: {resp.status_code}\n{resp.text}"
            )
        return resp.json()

    def _clear_deployment_ref(self, project_id: str) -> None:
        """Remove stale deployment_id from a project's extra metadata."""
        resp = requests.patch(
            f"{_SMITH_API_URL}/api/v1/sessions/{project_id}",
            headers=self.headers,
            json={"extra": {}},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f"Failed to clear deployment reference on {project_id}: "
                f"{resp.status_code}\n{resp.text}"
            )

    def delete_project(self, project_id: str, *, force: bool = False) -> bool:
        """
        Delete a tracing project by ID.

        If the project has a stale deployment reference (409) and force=True,
        the reference is cleared automatically before retrying the delete.
        Returns True on success, raises RuntimeError otherwise.
        """
        resp = requests.delete(
            f"{_SMITH_API_URL}/api/v1/sessions/{project_id}",
            headers=self.headers,
            timeout=_REQUEST_TIMEOUT,
        )

        if resp.status_code == HTTPStatus.ACCEPTED:
            return True

        if resp.status_code == HTTPStatus.CONFLICT:
            detail = resp.json().get("detail", resp.text)

            if "associated with a LangGraph deployment" not in detail:
                raise RuntimeError(f"409 Conflict: {detail}")

            if not force:
                raise RuntimeError(
                    f"409 Conflict: {detail}\n"
                    "Re-run with --force to automatically clear stale "
                    "deployment references."
                )

            # Deployment is orphaned — clear the reference and retry.
            self._clear_deployment_ref(project_id)
            retry = requests.delete(
                f"{_SMITH_API_URL}/api/v1/sessions/{project_id}",
                headers=self.headers,
                timeout=_REQUEST_TIMEOUT,
            )
            if retry.status_code == HTTPStatus.ACCEPTED:
                return True
            raise RuntimeError(
                f"Delete failed after clearing deployment reference: "
                f"{retry.status_code}\n{retry.text}"
            )

        raise RuntimeError(
            f"Failed to delete project {project_id}: {resp.status_code}\n{resp.text}"
        )


# =============================================================================
# Output formatters
# =============================================================================


def _print_table(projects: list[dict[str, Any]]) -> None:
    if not projects:
        click.echo("No projects found.")
        return

    id_w = max((len(project.get("id", "")) for project in projects), default=36)
    id_w = max(id_w, 4)
    name_w = max((len(project.get("name", "")) for project in projects), default=20)
    name_w = max(name_w, 4)
    runs_w = 6

    header = f"{'ID':<{id_w}}  {'Name':<{name_w}}  {'Runs':>{runs_w}}  Deployment ID"
    click.echo(f"\nFound {len(projects)} project(s):\n")
    click.echo(header)
    click.echo("-" * (len(header) + 10))

    for project in projects:
        dep_id = (project.get("extra") or {}).get("deployment_id", "")
        run_count = project.get("run_count", "")
        run_str = str(run_count) if run_count is not None else ""
        click.echo(
            f"{project.get('id', ''):<{id_w}}  {project.get('name', ''):<{name_w}}  "
            f"{run_str:>{runs_w}}  {dep_id}"
        )
    click.echo()


# =============================================================================
# CLI
# =============================================================================


def _api_key_option(func):
    return click.option(
        "--api-key",
        envvar="LANGSMITH_API_KEY",
        help="LangSmith API key (defaults to LANGSMITH_API_KEY env var)",
    )(func)


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Manage LangSmith tracing projects.

    \b
    PREREQUISITES:
    - LANGSMITH_API_KEY: Your LangSmith API key
    """
    pass


@cli.command("list")
@_api_key_option
@click.option("--name", help="Filter by exact project name")
@click.option(
    "--prefix",
    help="Filter by canonical name base (matches '<prefix>' and '<prefix>-*'); "
    "useful for finding a service's live project regardless of any rescue suffix",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table)",
)
def list_projects(
    api_key: str | None,
    name: str | None,
    prefix: str | None,
    output_format: str,
):
    """List tracing projects."""
    if name and prefix:
        raise click.UsageError("Provide either --name or --prefix, not both.")

    client = TracingProjectClient(api_key)

    try:
        if prefix:
            projects = client.list_projects_by_prefix(prefix, include_stats=True)
        else:
            projects = client.list_projects(name=name, include_stats=True)
    except RuntimeError as e:
        raise click.ClickException(str(e)) from e

    if output_format == "json":
        click.echo(json.dumps(projects, indent=2, default=str))
    else:
        _print_table(projects)


@cli.command()
@_api_key_option
@click.option("--name", required=True, help="Exact project name to inspect")
def info(api_key: str | None, name: str):
    """Show project metadata and trace statistics."""
    client = TracingProjectClient(api_key)

    try:
        projects = client.list_projects(name=name, include_stats=True)
    except RuntimeError as e:
        raise click.ClickException(str(e)) from e

    if not projects:
        raise click.ClickException(f"No project found with name: {name}")

    if len(projects) > 1:
        click.echo(
            click.style(
                f"Warning: {len(projects)} projects share the name '{name}'. "
                "Showing the first; use 'list --name' to see all or "
                "'delete --id' to target a specific one.",
                fg="yellow",
            )
        )
        for match in projects:
            click.echo(f"  - {match['id']}")

    project = projects[0]
    run_count = project.get("run_count", 0) or 0
    last_run = project.get("last_run_start_time") or "\u2014"
    dep_id = (project.get("extra") or {}).get("deployment_id") or "(none)"

    click.echo(f"\nProject: {project['name']}")
    click.echo(f"  ID:             {project['id']}")
    click.echo(f"  Run count:      {run_count}")
    click.echo(f"  Last run:       {last_run}")
    click.echo(f"  Deployment ID:  {dep_id}")
    click.echo()


def _resolve_targets(
    client: TracingProjectClient,
    project_id: str | None,
    name: str | None,
) -> list[dict[str, Any]]:
    """Resolve deletion targets from --id or --name.

    For --id, the project is fetched with stats so the trace-loss guard in
    ``_delete_one`` applies identically to both modes (an ID with no stats would
    otherwise be treated as having zero traces and bypass the guard).
    """
    if project_id:
        project = client.get_project_by_id(project_id)
        if not project:
            click.echo(f"No project found with id: {project_id}")
            return []
        return [project]

    targets = client.list_projects(name=name, include_stats=True)
    if not targets:
        click.echo(f"No projects found with name: {name}")
    else:
        click.echo(f"Found {len(targets)} project(s) named '{name}'")
    return targets


def _delete_one(
    client: TracingProjectClient,
    project: dict[str, Any],
    *,
    force: bool,
) -> str:
    """Attempt to delete a single project. Returns 'deleted', 'skipped', or 'failed'."""
    pid = project["id"]
    pname = project.get("name", pid)
    run_count = project.get("run_count", 0) or 0
    dep_id = (project.get("extra") or {}).get("deployment_id", "")

    if run_count > 0 and not force:
        click.echo(
            click.style(
                f"  Skipping '{pname}' [{pid}] — "
                f"has {run_count} trace(s). Use --force to delete.",
                fg="yellow",
            )
        )
        return "skipped"

    suffix = ""
    if dep_id and force:
        suffix = f" (orphaned deployment: {dep_id})"
    if run_count > 0:
        suffix += f" ({run_count} traces will be lost)"
    click.echo(f"  Deleting '{pname}' [{pid}]{suffix} ...")

    try:
        client.delete_project(pid, force=force)
        click.echo(click.style("    ✓ Deleted", fg="green"))
    except RuntimeError as e:
        click.echo(click.style(f"    ✗ {e}", fg="red"))
        return "failed"
    return "deleted"


@cli.command()
@_api_key_option
@click.option("--id", "project_id", help="Project ID to delete")
@click.option("--name", help="Delete all projects matching this exact name")
@click.option(
    "--force",
    is_flag=True,
    help=(
        "Delete even if the project contains traces, and clear stale "
        "deployment references to unblock deletion"
    ),
)
@click.confirmation_option(prompt="Are you sure you want to delete this project?")
def delete(
    api_key: str | None,
    project_id: str | None,
    name: str | None,
    force: bool,
):
    """Delete one or more tracing projects.

    \b
    Provide either --id for a single project or --name to delete all
    projects with that exact name.

    \b
    Use --force to:
    - Delete projects that still contain traces (data loss)
    - Clear stale deployment references (orphaned deployments)
    """
    if not project_id and not name:
        raise click.UsageError("Provide either --id or --name.")
    if project_id and name:
        raise click.UsageError("Provide either --id or --name, not both.")

    client = TracingProjectClient(api_key)

    try:
        targets = _resolve_targets(client, project_id, name)
    except RuntimeError as e:
        raise click.ClickException(str(e)) from e

    if not targets:
        return

    results = [_delete_one(client, target, force=force) for target in targets]

    click.echo()
    deleted = results.count("deleted")
    skipped = results.count("skipped")
    failed = results.count("failed")
    if deleted:
        click.echo(click.style(f"{deleted} project(s) deleted.", fg="green"))
    if skipped:
        click.echo(
            click.style(f"{skipped} project(s) skipped (have traces).", fg="yellow")
        )
    if failed:
        click.echo(click.style(f"{failed} project(s) failed.", fg="red"))


if __name__ == "__main__":
    cli()
