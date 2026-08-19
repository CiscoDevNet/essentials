"""Click CLI utilities for LangSmith Control Plane scripts."""

from typing import Any, TypeVar

import click

from ess_langsmith_client.client import ControlPlaneClient
from ess_langsmith_client.naming import resolve_deploy_base

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


def env_option(func):
    """Add the --env option used to build the canonical <service>-<env> name.

    Defaults are resolved by ``ess_langsmith_client.naming.resolve_env``: the flag
    value wins, then the ``APP_ENV`` environment variable, then ``dev``.
    """
    return click.option(
        "--env",
        "env",
        default=None,
        help=(
            "Deployment environment, e.g. dev or prod "
            "(defaults to $APP_ENV, then 'dev')"
        ),
    )(func)


def deployment_option(func):
    """Add ``--deployment`` for a full base name (skips ``<service>-<env>``)."""
    return click.option(
        "--deployment",
        default=None,
        help=(
            "Full deployment base name; uses this value as-is instead of "
            "building <service>-<env> from --name and --env"
        ),
    )(func)


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


def resolve_live_deployment_record(
    client: ControlPlaneClient,
    *,
    deployment: str | None = None,
    service: str | None = None,
    env: str | None = None,
) -> dict[str, Any] | None:
    """Return the live deployment record for a base name, or None."""
    base = resolve_deploy_base(deployment=deployment, service=service, env=env)
    return client.resolve_live_deployment(base)


def resolve_deployment_base_url(  # noqa: PLR0913  # one param per resolution/cred input
    service: str,
    *,
    deployment: str | None = None,
    env: str | None = None,
    region: str = "us",
    api_key: str | None = None,
    workspace_id: str | None = None,
) -> str:
    """Resolve a deployed agent's public base URL from the Control Plane.

    Looks up the live deployment for the explicit ``deployment`` name (or the
    canonical ``<service>-<env>`` base) and returns its
    ``source_config.custom_url`` -- the ingress "nice URL" including the
    ``/lgp/<hash>`` mount prefix. This lets test tooling reach a deployed agent
    over its public URL without kubectl or the raw mount prefix.

    Args:
        service: Service name used to build the canonical ``<service>-<env>``
            base name when ``deployment`` is not given.
        deployment: Explicit deployment (base) name to resolve. Overrides the
            canonical name derived from ``service``/``env``.
        env: Environment for the canonical name (resolved via ``resolve_env``:
            the value, then ``$APP_ENV``, then ``dev``).
        region: LangSmith Control Plane region ("us" or "eu").
        api_key: LangSmith API key (defaults to ``LANGSMITH_API_KEY``).
        workspace_id: LangSmith workspace ID (defaults to
            ``LANGSMITH_WORKSPACE_ID``).

    Returns:
        The deployment's public base URL (hostname + ``/lgp/<hash>`` prefix).

    Raises:
        click.ClickException: if credentials are missing, no live deployment
            matches, or the deployment exposes no ingress ``custom_url``.
    """
    try:
        base = resolve_deploy_base(deployment=deployment, service=service, env=env)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Resolving deployment '{base}' via LangSmith Control Plane...")
    client = create_client(ControlPlaneClient, api_key, workspace_id, region)
    deployment_record = resolve_live_deployment_record(
        client,
        deployment=deployment,
        service=service,
        env=env,
    )
    if not deployment_record:
        raise click.ClickException(
            f"No live deployment found for '{base}'. "
            "Pass --deployment <name> or check --env/--region."
        )
    custom_url = (deployment_record.get("source_config") or {}).get("custom_url")
    if not custom_url:
        raise click.ClickException(
            f"Deployment '{deployment_record.get('name', base)}' has no custom_url "
            "(no ingress hostname configured). Use --prefix or --kubectl instead."
        )
    click.echo(f"  Found: {custom_url}")
    return custom_url


def echo_success(message: str) -> None:
    """Print a success message in green."""
    click.echo(click.style(message, fg="green"))


def echo_deployment_created(deployment_id: str, revision_id: str | None) -> None:
    """Print deployment created output."""
    echo_success("\nDeployment created!")
    click.echo(f"  Deployment ID: {deployment_id}")
    click.echo(f"  Revision ID: {revision_id}")


def echo_deployment_resolved(
    action: str,
    name: str,
    deployment_id: str,
    revision_id: str | None = None,
    url: str | None = None,
) -> None:
    """Print the resolved deployment name, ID, and URL after a deploy.

    ``action`` is a short verb such as "created" or "updated". This is the
    canonical way to surface which name/ID a deploy converged on, so the active
    name is always visible without having to know any rescue suffix.
    """
    echo_success(f"\nDeployment {action}: {name}")
    click.echo(f"  Deployment ID: {deployment_id}")
    if revision_id:
        click.echo(f"  Revision ID: {revision_id}")
    if url:
        click.echo(f"  URL: {url}")


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
