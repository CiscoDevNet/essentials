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
    langsmith-build --push --registry your-registry

CONTROL PLANE API REFERENCE:
    https://docs.langchain.com/langsmith/api-ref-control-plane
"""

import re
from pathlib import Path
from typing import Any

import click
import requests

from langsmith_client import (
    ControlPlaneClient,
    common_options,
    create_client,
    echo_deployment_created,
    echo_success,
    get_project_info,
    handle_wait,
    merge_secrets,
    print_deployments,
)

HTTP_OK = 200
HTTP_CREATED = 201

_REQUEST_TIMEOUT = 30


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

    def create_deployment(  # noqa: PLR0913
        self,
        name: str,
        image_uri: str,
        listener_id: str | None = None,
        k8s_namespace: str | None = None,
        secrets: list[dict[str, str]] | None = None,
        env_vars: list[dict[str, str]] | None = None,
        min_scale: int = 1,
        max_scale: int = 3,
        cpu: int = 1,
        memory_mb: int = 1024,
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

        if response.status_code in (HTTP_OK, HTTP_CREATED):
            return response.json()
        raise RuntimeError(
            f"Failed to create deployment: {response.status_code}\n{response.text}"
        )

    def update_deployment(
        self,
        deployment_id: str,
        image_uri: str,
        secrets: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Update an existing Docker deployment with a new image."""
        request_body: dict[str, Any] = {
            "source_revision_config": {
                "repo_ref": None,
                "langgraph_config_path": None,
                "image_uri": image_uri,
            }
        }
        if secrets:
            request_body["secrets"] = secrets

        response = requests.patch(
            f"{self.base_url}/deployments/{deployment_id}",
            headers=self.headers,
            json=request_body,
            timeout=_REQUEST_TIMEOUT,
        )

        if response.status_code == HTTP_OK:
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
@_project_dir_option
@click.option(
    "--name", help="Deployment name (defaults to project name from pyproject.toml)"
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
def create(  # noqa: PLR0913
    region: str,
    api_key: str | None,
    workspace_id: str | None,
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
    """Create a new deployment from a Docker image."""
    client = create_client(DockerDeploymentClient, api_key, workspace_id, region)

    # Get project info from pyproject.toml
    project = get_project_info(start_path=Path(project_dir))

    # Derive name from project or image URI
    if not name:
        if project:
            name = project.name
        elif image_uri:
            name = extract_name_from_image_uri(image_uri)
        else:
            raise click.ClickException(
                "Could not determine deployment name. "
                "Provide --name or ensure pyproject.toml exists with [project].name"
            )

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

    click.echo(f"Creating Docker deployment: {name}")
    click.echo(f"  Image: {image_uri}")
    click.echo(f"  Scale: {min_scale}-{max_scale} instances")

    try:
        result = client.create_deployment(
            name=name,
            image_uri=image_uri,
            listener_id=listener_id,
            k8s_namespace=k8s_namespace,
            secrets=merge_secrets(secrets),
            min_scale=min_scale,
            max_scale=max_scale,
            cpu=cpu,
            memory_mb=memory,
        )

        echo_deployment_created(result["id"], result.get("latest_revision_id"))
        handle_wait(client, result["id"], result.get("latest_revision_id"), wait)

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
def update(  # noqa: PLR0913
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
        click.echo(f"  Secrets: {', '.join(s['name'] for s in secret_list)}")

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
                d for d in deployments if d.get("source") == "external_docker"
            ]

        print_deployments(deployments)

    except RuntimeError as e:
        raise click.ClickException(str(e)) from e


@cli.command()
@common_options
@click.option("--deployment-id", required=True, help="Deployment ID to delete")
@click.confirmation_option(prompt="Are you sure you want to delete this deployment?")
def delete(
    region: str,
    api_key: str | None,
    workspace_id: str | None,
    deployment_id: str,
):
    """Delete a deployment."""
    client = create_client(DockerDeploymentClient, api_key, workspace_id, region)

    click.echo(f"Deleting deployment: {deployment_id}")

    try:
        client.delete_deployment(deployment_id)
        echo_success("Deployment deleted successfully!")

    except RuntimeError as e:
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    cli()
