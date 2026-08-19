#!/usr/bin/env python3
"""
Deploy LangGraph agents to LangSmith from a Docker image.

This tool uses the LangSmith Control Plane API to create deployments from
Docker images. This is the approach for self-hosted or hybrid LangSmith deployments.

PREREQUISITES:
- LANGSMITH_API_KEY: Your LangSmith API key
- LANGSMITH_WORKSPACE_ID: Your LangSmith workspace ID (found in workspace settings)
- A Docker image pushed to a container registry accessible by LangSmith

BUILD AND PUSH WORKFLOW:
    langsmith-client build --push --registry your-registry

Deployments use a stable canonical name of the form <service>-<env>, where
service defaults to [project].name from pyproject.toml (override with --name)
and env comes from --env (defaults to $APP_ENV, then "dev"). Pass --deployment
to use a full base name as-is (for example my-agent-prod-dev) without
splitting service and env.

Re-running ``create`` is an idempotent upsert: it updates the live deployment
in place, or creates a git-SHA rescue name only when the canonical name is
stuck/orphaned.

CONTROL PLANE API REFERENCE:
    https://docs.langchain.com/langsmith/api-ref-control-plane
"""

# Click command callbacks expose one function parameter per CLI option, and the
# deployment-creation helper takes one per tunable deployment setting, so the
# argument count necessarily exceeds PLR0913's limit. Suppress it module-wide.
# ruff: noqa: PLR0913

import re
from http import HTTPStatus
from pathlib import Path
from typing import Any

import click
import requests

from ess_langsmith_client import (
    ControlPlaneClient,
    choose_deploy_name,
    common_options,
    create_client,
    deployment_option,
    echo_deployment_resolved,
    echo_success,
    env_option,
    get_git_sha,
    get_project_info,
    handle_wait,
    merge_secrets,
    print_deployments,
    resolve_live_deployment_record,
)
from ess_langsmith_client.client import _REQUEST_TIMEOUT
from ess_langsmith_client.naming import resolve_deploy_base


def extract_name_from_image_uri(image_uri: str) -> str:
    """
    Extract a deployment name from a Docker image URI.

    Examples:
        registry/my-agent:latest -> my-agent
        gcr.io/project/hello-world:v1 -> hello-world
    """
    # Remove tag, get last path component, sanitize
    name = image_uri.split(":", maxsplit=1)[0].rsplit("/", maxsplit=1)[-1]
    return re.sub(r"[^a-zA-Z0-9_-]", "-", name)


class DockerDeploymentClient(ControlPlaneClient):
    """Client for Docker-based deployments to LangSmith."""

    def create_deployment(
        self,
        name: str,
        image_uri: str,
        listener_id: str | None = None,
        k8s_namespace: str | None = None,
        secrets: list[dict[str, str]] | None = None,
        env_vars: list[dict[str, str]] | None = None,
        min_scale: int = 2,
        max_scale: int = 10,
        cpu: int = 4,
        memory_mb: int = 8192,
    ) -> dict[str, Any]:
        """Create a new deployment from a Docker image."""
        source_config: dict[str, Any] = {
            "integration_id": None,
            "repo_url": None,
            "deployment_type": None,
            "build_on_push": None,
            "custom_url": None,
            "resource_spec": {
                "min_scale": min_scale,
                "max_scale": max_scale,
                "cpu": cpu,
                "memory_mb": memory_mb,
            },
        }

        if listener_id:
            source_config["listener_id"] = listener_id
        if k8s_namespace:
            source_config["listener_config"] = {"k8s_namespace": k8s_namespace}

        request_body = {
            "name": name,
            "source": "external_docker",
            "source_config": source_config,
            "source_revision_config": {
                "repo_ref": None,
                "langgraph_config_path": None,
                "image_uri": image_uri,
            },
            "secrets": secrets or [],
            "env_vars": env_vars or [],
        }

        response = requests.post(
            f"{self.base_url}/deployments",
            headers=self.headers,
            json=request_body,
            timeout=_REQUEST_TIMEOUT,
        )

        if response.status_code in (HTTPStatus.OK, HTTPStatus.CREATED):
            return response.json()
        raise RuntimeError(
            f"Failed to create deployment: {response.status_code}\n{response.text}"
        )

    def update_deployment(
        self,
        deployment_id: str,
        image_uri: str,
        secrets: list[dict[str, str]] | None = None,
        min_scale: int | None = None,
        max_scale: int | None = None,
        cpu: int | None = None,
        memory_mb: int | None = None,
    ) -> dict[str, Any]:
        """Update an existing Docker deployment with a new image and spec.

        Passing any of ``min_scale``/``max_scale``/``cpu``/``memory_mb`` applies
        the resource spec so re-deploying reconciles the desired scale/resources,
        not just the image. Listener and Kubernetes namespace are placement
        settings fixed at creation time and are not updated here.
        """
        request_body: dict[str, Any] = {
            "source_revision_config": {
                "repo_ref": None,
                "langgraph_config_path": None,
                "image_uri": image_uri,
            }
        }
        if secrets:
            request_body["secrets"] = secrets

        resource_spec = {
            key: value
            for key, value in {
                "min_scale": min_scale,
                "max_scale": max_scale,
                "cpu": cpu,
                "memory_mb": memory_mb,
            }.items()
            if value is not None
        }
        if resource_spec:
            request_body["source_config"] = {"resource_spec": resource_spec}

        response = requests.patch(
            f"{self.base_url}/deployments/{deployment_id}",
            headers=self.headers,
            json=request_body,
            timeout=_REQUEST_TIMEOUT,
        )

        if response.status_code == HTTPStatus.OK:
            return response.json()
        raise RuntimeError(
            f"Failed to update deployment: {response.status_code}\n{response.text}"
        )


def _project_dir_option(func):
    """Add --project-dir / -C option to a command."""
    return click.option(
        "--project-dir",
        "-C",
        type=click.Path(exists=True, file_okay=False, resolve_path=True),
        default=".",
        help="Project directory containing pyproject.toml (default: current directory)",
    )(func)


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Deploy LangGraph agents to LangSmith from Docker images.

    \b
    PREREQUISITES:
    - LANGSMITH_API_KEY: Your LangSmith API key
    - LANGSMITH_WORKSPACE_ID: Your workspace ID (from LangSmith settings)
    - A Docker image pushed to an accessible container registry
    """
    pass


@cli.command()
@common_options
@env_option
@deployment_option
@_project_dir_option
@click.option(
    "--name",
    help="Service name for the canonical <service>-<env> name "
    "(defaults to project name from pyproject.toml)",
)
@click.option("--image-uri", help="Docker image URI (defaults to project-name:version)")
@click.option(
    "--listener-id",
    envvar="LANGSMITH_LISTENER_ID",
    help=(
        "Listener ID for hybrid deployments (defaults to LANGSMITH_LISTENER_ID env var)"
    ),
)
@click.option(
    "--namespace",
    "k8s_namespace",
    default="default",
    help="Kubernetes namespace to deploy to (default: default)",
)
@click.option("--secret", "secrets", multiple=True, help="Secret in NAME=VALUE format")
@click.option("--min-scale", type=int, default=1, help="Minimum instances")
@click.option("--max-scale", type=int, default=3, help="Maximum instances")
@click.option("--cpu", type=int, default=1, help="CPU cores per instance")
@click.option("--memory", type=int, default=1024, help="Memory in MB")
@click.option("--wait", is_flag=True, help="Wait for deployment to complete")
def create(
    region: str,
    api_key: str | None,
    workspace_id: str | None,
    env: str | None,
    deployment: str | None,
    project_dir: str,
    name: str | None,
    image_uri: str | None,
    listener_id: str | None,
    k8s_namespace: str,
    secrets: tuple[str, ...],
    min_scale: int,
    max_scale: int,
    cpu: int,
    memory: int,
    wait: bool,
):
    """Deploy a Docker image to LangSmith (idempotent upsert).

    \b
    Resolves the canonical <service>-<env> name and:
    - updates the live deployment in place if one exists,
    - creates the canonical name if none exists,
    - creates a git-SHA rescue name (<service>-<env>-<sha>) only when the
      canonical name is stuck/orphaned.
    """
    client = create_client(DockerDeploymentClient, api_key, workspace_id, region)

    # Get project info from pyproject.toml
    project = get_project_info(start_path=Path(project_dir))

    # Derive the service name from --name, the project, or the image URI.
    service = name
    if not service and not deployment:
        if project:
            service = project.name
        elif image_uri:
            service = extract_name_from_image_uri(image_uri)
        else:
            raise click.ClickException(
                "Could not determine deployment name. "
                "Provide --deployment, --name, or ensure pyproject.toml exists "
                "with [project].name"
            )

    try:
        base = resolve_deploy_base(deployment=deployment, service=service, env=env)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    # Derive image URI from project if not provided
    if not image_uri:
        if project:
            image_uri = f"{project.name}:{project.version}"
            click.echo(f"Using image from pyproject.toml: {image_uri}")
        else:
            raise click.ClickException(
                "Could not determine image URI. "
                "Provide --image-uri or ensure pyproject.toml exists"
            )

    secret_list = merge_secrets(secrets)

    try:
        live = client.resolve_live_deployment(base)

        if live:
            click.echo(f"Updating live deployment '{live['name']}' [{live['id']}]")
            click.echo(f"  Image: {image_uri}")
            click.echo(f"  Scale: {min_scale}-{max_scale} instances")
            result = client.update_deployment(
                deployment_id=live["id"],
                image_uri=image_uri,
                secrets=secret_list,
                min_scale=min_scale,
                max_scale=max_scale,
                cpu=cpu,
                memory_mb=memory,
            )
            revision_id = result.get("latest_revision_id")
            echo_deployment_resolved(
                "updated", live["name"], live["id"], revision_id, live.get("url")
            )
            handle_wait(client, live["id"], revision_id, wait, live.get("url"))
            return

        taken = {
            deployment["name"] for deployment in client.find_deployments_by_base(base)
        }
        deploy_name = choose_deploy_name(base, taken, get_git_sha())
        if deploy_name != base:
            click.echo(
                click.style(
                    f"Canonical name '{base}' is stuck/orphaned; "
                    f"using rescue name '{deploy_name}'.",
                    fg="yellow",
                )
            )
        click.echo(f"Creating Docker deployment: {deploy_name}")
        click.echo(f"  Image: {image_uri}")
        click.echo(f"  Scale: {min_scale}-{max_scale} instances")

        result = client.create_deployment(
            name=deploy_name,
            image_uri=image_uri,
            listener_id=listener_id,
            k8s_namespace=k8s_namespace,
            secrets=secret_list,
            min_scale=min_scale,
            max_scale=max_scale,
            cpu=cpu,
            memory_mb=memory,
        )

        revision_id = result.get("latest_revision_id")
        echo_deployment_resolved(
            "created", deploy_name, result["id"], revision_id, result.get("url")
        )
        handle_wait(client, result["id"], revision_id, wait, result.get("url"))

    except RuntimeError as e:
        raise click.ClickException(str(e)) from e


@cli.command()
@common_options
@_project_dir_option
@click.option("--deployment-id", required=True, help="Deployment ID to update")
@click.option(
    "--image-uri",
    help="New Docker image URI (defaults to name:version from pyproject.toml)",
)
@click.option(
    "--secret",
    "secrets",
    multiple=True,
    help="Secret in NAME=VALUE or NAME=$ENV_VAR format",
)
@click.option("--wait", is_flag=True, help="Wait for deployment to complete")
def update(
    region: str,
    api_key: str | None,
    workspace_id: str | None,
    project_dir: str,
    deployment_id: str,
    image_uri: str | None,
    secrets: tuple[str, ...],
    wait: bool,
):
    """Update an existing deployment with a new Docker image."""
    # Derive image URI from pyproject.toml if not provided
    if not image_uri:
        project = get_project_info(start_path=Path(project_dir))
        if project:
            image_uri = f"{project.name}:{project.version}"
            click.echo(f"Using image from pyproject.toml: {image_uri}")
        else:
            raise click.ClickException(
                "Could not determine image URI. "
                "Provide --image-uri or ensure pyproject.toml exists"
            )
    client = create_client(DockerDeploymentClient, api_key, workspace_id, region)

    secret_list = merge_secrets(secrets)

    click.echo(f"Updating deployment: {deployment_id}")
    click.echo(f"  New image: {image_uri}")
    if secret_list:
        click.echo(f"  Secrets: {', '.join(secret['name'] for secret in secret_list)}")

    try:
        result = client.update_deployment(
            deployment_id=deployment_id,
            image_uri=image_uri,
            secrets=secret_list,
        )

        revision_id = result.get("latest_revision_id")
        click.echo(f"  New revision ID: {revision_id}")
        handle_wait(client, deployment_id, revision_id, wait)

    except RuntimeError as e:
        raise click.ClickException(str(e)) from e


@cli.command("list")
@common_options
@click.option("--filter", "name_filter", help="Filter by name (contains)")
@click.option("--docker-only", is_flag=True, help="Show only Docker deployments")
def list_deployments(
    region: str,
    api_key: str | None,
    workspace_id: str | None,
    name_filter: str | None,
    docker_only: bool,
):
    """List deployments."""
    client = create_client(DockerDeploymentClient, api_key, workspace_id, region)

    click.echo("Fetching deployments...")

    try:
        result = client.list_deployments(name_contains=name_filter)
        deployments = result.get("resources", [])

        if docker_only:
            deployments = [
                deployment
                for deployment in deployments
                if deployment.get("source") == "external_docker"
            ]

        print_deployments(deployments)

    except RuntimeError as e:
        raise click.ClickException(str(e)) from e


@cli.command()
@common_options
@env_option
@deployment_option
@_project_dir_option
@click.option(
    "--name",
    help="Service name (defaults to [project].name in pyproject.toml)",
)
@click.option(
    "--deployment-id",
    help="Deployment ID to delete (alternative to -C / --deployment resolution)",
)
@click.option(
    "--if-exists",
    is_flag=True,
    help="Exit 0 when no live deployment matches the resolved base name",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
def delete(
    region: str,
    api_key: str | None,
    workspace_id: str | None,
    env: str | None,
    deployment: str | None,
    project_dir: str,
    name: str | None,
    deployment_id: str | None,
    if_exists: bool,
    yes: bool,
):
    """Delete a deployment by ID or by resolved ``<service>-<env>`` base name."""
    client = create_client(DockerDeploymentClient, api_key, workspace_id, region)

    target_id = deployment_id
    target_name: str | None = None

    if not target_id:
        project = get_project_info(start_path=Path(project_dir))
        service = name
        if not service and not deployment:
            if project:
                service = project.name
            else:
                raise click.ClickException(
                    "Provide --deployment-id, --deployment, or -C with pyproject.toml"
                )
        try:
            base = resolve_deploy_base(deployment=deployment, service=service, env=env)
            live = resolve_live_deployment_record(
                client,
                deployment=deployment,
                service=service,
                env=env,
            )
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        if not live:
            if if_exists:
                click.echo(f"No live deployment found for '{base}'. Nothing to delete.")
                return
            raise click.ClickException(
                f"No live deployment found for '{base}'. "
                "Pass --deployment-id or check --env/$APP_ENV."
            )
        target_id = live["id"]
        target_name = live.get("name")

    display = f"{target_name} [{target_id}]" if target_name else target_id
    if not yes:
        click.confirm(
            f"Are you sure you want to delete deployment {display}?",
            abort=True,
        )
    click.echo(f"Deleting deployment: {display}")

    try:
        client.delete_deployment(target_id)
        echo_success("Deployment deleted successfully!")

    except RuntimeError as e:
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    cli()
