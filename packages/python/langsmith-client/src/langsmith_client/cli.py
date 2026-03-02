"""Click CLI utilities for LangSmith Control Plane scripts."""

from typing import Any, TypeVar

import click

from langsmith_client.client import ControlPlaneClient

T = TypeVar("T", bound=ControlPlaneClient)


def common_options(func):
    """Decorator to add common CLI options (region, api-key, workspace-id)."""
    func = click.option(
        "--region",
        type=click.Choice(["us", "eu"]),
        default="us",
        help="LangSmith region",
    )(func)
    func = click.option(
        "--api-key",
        envvar="LANGSMITH_API_KEY",
        help="LangSmith API key",
    )(func)
    func = click.option(
        "--workspace-id",
        envvar="LANGSMITH_WORKSPACE_ID",
        help="LangSmith workspace ID",
    )(func)
    return func


def create_client(
    client_class: type[T],
    api_key: str | None,
    workspace_id: str | None,
    region: str,
) -> T:
    """Create a client instance, converting ValueError to ClickException."""
    try:
        return client_class(
            api_key=api_key,
            workspace_id=workspace_id,
            region=region,
        )
    except ValueError as e:
        raise click.ClickException(str(e)) from e


def echo_success(message: str) -> None:
    """Print a success message in green."""
    click.echo(click.style(message, fg="green"))


def echo_deployment_created(deployment_id: str, revision_id: str | None) -> None:
    """Print deployment created output."""
    echo_success("\nDeployment created!")
    click.echo(f"  Deployment ID: {deployment_id}")
    click.echo(f"  Revision ID: {revision_id}")


def print_deployments(deployments: list[dict[str, Any]]) -> None:
    """Print a formatted list of deployments."""
    if not deployments:
        click.echo("No deployments found.")
        return

    click.echo(f"\nFound {len(deployments)} deployment(s):\n")
    for dep in deployments:
        click.echo(f"  ID: {dep['id']}")
        click.echo(f"  Name: {dep['name']}")
        click.echo(f"  Source: {dep.get('source', 'N/A')}")
        click.echo(f"  Status: {dep.get('status', 'N/A')}")
        if dep.get("url"):
            click.echo(f"  URL: {dep['url']}")
        click.echo()


def handle_wait(
    client: ControlPlaneClient,
    deployment_id: str,
    revision_id: str | None,
    wait: bool,
    url: str | None = None,
) -> None:
    """Handle the --wait flag for deployment commands."""
    if wait and revision_id:
        click.echo("\nWaiting for deployment to complete...")
        try:
            final = client.wait_for_deployment(deployment_id, revision_id)
            echo_success("\nDeployment complete!")
            click.echo(f"  Status: {final.get('status')}")
            if url:
                click.echo(f"  URL: {url}")
        except RuntimeError as e:
            raise click.ClickException(str(e)) from e
