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
    langsmith-projects list
    langsmith-projects list --name hello-world-graph
    langsmith-projects delete --id <uuid>
    langsmith-projects delete --name hello-world-graph
    langsmith-projects delete --name hello-world --force
"""

import json
import os
from typing import Any

import click
import requests
from dotenv import load_dotenv

load_dotenv()

SMITH_API = "https://api.smith.langchain.com"

HTTP_OK = 200
HTTP_ACCEPTED = 202
HTTP_CONFLICT = 409

_REQUEST_TIMEOUT = 30


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

    def list_projects(self, name: str | None = None) -> list[dict[str, Any]]:
        """List tracing projects, optionally filtered by exact name."""
        params: dict[str, str] = {}
        if name:
            params["name"] = name
        resp = requests.get(
            f"{SMITH_API}/api/v1/sessions",
            headers=self.headers,
            params=params,
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != HTTP_OK:
            raise RuntimeError(
                f"Failed to list projects: {resp.status_code}\n{resp.text}"
            )
        return resp.json()

    def _clear_deployment_ref(self, project_id: str) -> None:
        """Remove stale deployment_id from a project's extra metadata."""
        resp = requests.patch(
            f"{SMITH_API}/api/v1/sessions/{project_id}",
            headers=self.headers,
            json={"extra": {}},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != HTTP_OK:
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
            f"{SMITH_API}/api/v1/sessions/{project_id}",
            headers=self.headers,
            timeout=_REQUEST_TIMEOUT,
        )

        if resp.status_code == HTTP_ACCEPTED:
            return True

        if resp.status_code == HTTP_CONFLICT:
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
                f"{SMITH_API}/api/v1/sessions/{project_id}",
                headers=self.headers,
                timeout=_REQUEST_TIMEOUT,
            )
            if retry.status_code == HTTP_ACCEPTED:
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

    id_w = max((len(p.get("id", "")) for p in projects), default=36)
    id_w = max(id_w, 4)
    name_w = max((len(p.get("name", "")) for p in projects), default=20)
    name_w = max(name_w, 4)

    header = f"{'ID':<{id_w}}  {'Name':<{name_w}}  Deployment ID"
    click.echo(f"\nFound {len(projects)} project(s):\n")
    click.echo(header)
    click.echo("-" * (len(header) + 10))

    for p in projects:
        dep_id = p.get("extra", {}).get("deployment_id", "")
        click.echo(
            f"{p.get('id', ''):<{id_w}}  {p.get('name', ''):<{name_w}}  {dep_id}"
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
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table)",
)
def list_projects(api_key: str | None, name: str | None, output_format: str):
    """List tracing projects."""
    client = TracingProjectClient(api_key)

    try:
        projects = client.list_projects(name=name)
    except RuntimeError as e:
        raise click.ClickException(str(e)) from e

    if output_format == "json":
        click.echo(json.dumps(projects, indent=2, default=str))
    else:
        _print_table(projects)


@cli.command()
@_api_key_option
@click.option("--id", "project_id", help="Project ID to delete")
@click.option("--name", help="Delete all projects matching this exact name")
@click.option(
    "--force",
    is_flag=True,
    help="Clear stale deployment references to unblock deletion",
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
    Use --force when a project is blocked by a stale deployment reference
    (the linked deployment no longer exists but was not properly cleaned up).
    """
    if not project_id and not name:
        raise click.UsageError("Provide either --id or --name.")
    if project_id and name:
        raise click.UsageError("Provide either --id or --name, not both.")

    client = TracingProjectClient(api_key)

    targets: list[dict[str, Any]] = []

    try:
        if project_id:
            targets = [{"id": project_id, "name": project_id}]
        else:
            targets = client.list_projects(name=name)
            if not targets:
                click.echo(f"No projects found with name: {name}")
                return
            click.echo(f"Found {len(targets)} project(s) named '{name}'")
    except RuntimeError as e:
        raise click.ClickException(str(e)) from e

    deleted = 0
    failed = 0
    for project in targets:
        pid = project["id"]
        pname = project.get("name", pid)
        dep_id = project.get("extra", {}).get("deployment_id", "")
        suffix = f" (orphaned deployment: {dep_id})" if dep_id and force else ""
        click.echo(f"  Deleting '{pname}' [{pid}]{suffix} ...")

        try:
            client.delete_project(pid, force=force)
            click.echo(click.style("    ✓ Deleted", fg="green"))
            deleted += 1
        except RuntimeError as e:
            click.echo(click.style(f"    ✗ {e}", fg="red"))
            failed += 1

    click.echo()
    if deleted:
        click.echo(click.style(f"{deleted} project(s) deleted.", fg="green"))
    if failed:
        click.echo(click.style(f"{failed} project(s) failed.", fg="red"))


if __name__ == "__main__":
    cli()
