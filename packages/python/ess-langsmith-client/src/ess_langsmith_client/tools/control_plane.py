#!/usr/bin/env python3
"""
Manage LangSmith Control Plane resources.

The control plane (``api.host.langchain.com`` on SaaS) owns deployments and
their backing "project" records at ``/v1/projects/{id}``. This CLI groups those
resources under one command so you do not have to remember individual endpoints.

Control-plane projects are distinct from tracing projects (sessions). Deleting a
control-plane project here does NOT delete traces unless you explicitly pass
``--delete-tracing-project``. To manage tracing projects, use
``langsmith-client projects``.

PREREQUISITES:
- LANGSMITH_API_KEY: A LangSmith API key with workspace-admin role
- A workspace ID: passed via --workspace-id or LANGSMITH_WORKSPACE_ID. The SaaS
  control plane requires it (sent as the X-Tenant-Id header) to route requests.

USAGE:
    langsmith-client control-plane projects delete --id <uuid> --workspace-id <uuid>
    langsmith-client control-plane projects delete --id <uuid> --id <uuid> --yes

CONTROL PLANE API REFERENCE:
    https://docs.langchain.com/langsmith/api-ref-control-plane
"""

import click

from ess_langsmith_client import (
    ControlPlaneClient,
    common_options,
    create_client,
    echo_success,
)
from ess_langsmith_client._version import get_package_version


@click.group()
@click.version_option(version=get_package_version())
def cli():
    """Manage LangSmith Control Plane resources.

    \b
    PREREQUISITES:
    - LANGSMITH_API_KEY: A LangSmith API key with workspace-admin role
    - A workspace ID via --workspace-id or LANGSMITH_WORKSPACE_ID (sent as
      X-Tenant-Id; required by the SaaS control plane)
    """
    pass


@cli.group()
def projects():
    """Manage control-plane project records.

    \b
    These are distinct from tracing projects (sessions). Use
    'langsmith-client projects' to manage tracing projects and their traces.
    """
    pass


@projects.command()
@common_options
@click.option(
    "--id",
    "project_ids",
    multiple=True,
    required=True,
    help="Control-plane project ID to delete (repeatable)",
)
@click.option(
    "--force/--no-force",
    default=True,
    help="Force deletion, clearing stale references that block it (default: on)",
)
@click.option(
    "--delete-tracing-project",
    is_flag=True,
    default=False,
    help=(
        "Also delete the paired tracing project and its traces. "
        "Off by default so trace data is preserved."
    ),
)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
def delete(  # noqa: PLR0913 — Click option surface; one param per flag is idiomatic
    region: str,
    api_key: str | None,
    workspace_id: str | None,
    project_ids: tuple[str, ...],
    force: bool,
    delete_tracing_project: bool,
    yes: bool,
):
    """Delete one or more control-plane project records by ID."""
    # The SaaS control plane routes by tenant, so a workspace (X-Tenant-Id) is
    # required. Fail early with a clear message instead of a confusing 404.
    if not workspace_id:
        raise click.ClickException(
            "A workspace is required: pass --workspace-id or set "
            "LANGSMITH_WORKSPACE_ID (sent as X-Tenant-Id)."
        )

    # The API key authorizes; the workspace is selected at runtime (below),
    # so it is not needed to instantiate the client.
    client = create_client(ControlPlaneClient, api_key, None, region)

    click.echo(f"About to delete {len(project_ids)} control-plane project(s):")
    for project_id in project_ids:
        click.echo(f"  - {project_id}")
    if delete_tracing_project:
        click.echo(
            click.style(
                "  --delete-tracing-project is set: traces WILL be deleted.",
                fg="yellow",
            )
        )

    if not yes:
        click.confirm("Proceed?", abort=True)

    failed = 0
    for project_id in project_ids:
        click.echo(f"Deleting '{project_id}' ...")
        try:
            client.delete_project(
                project_id,
                workspace_id=workspace_id,
                force=force,
                delete_tracing_project=delete_tracing_project,
            )
            echo_success("  Deleted")
        except RuntimeError as e:
            click.echo(click.style(f"  {e}", fg="red"))
            failed += 1

    click.echo()
    deleted = len(project_ids) - failed
    if deleted:
        echo_success(f"{deleted} project(s) deleted.")
    if failed:
        raise click.ClickException(f"{failed} project(s) failed to delete.")


if __name__ == "__main__":
    cli()
