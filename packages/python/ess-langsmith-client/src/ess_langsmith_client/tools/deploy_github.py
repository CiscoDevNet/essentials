#!/usr/bin/env python3
"""
Deploy LangGraph agents to LangSmith from a GitHub repository.

This tool uses the LangSmith Control Plane API to create deployments that
pull code from GitHub. This is the recommended approach for LangSmith Cloud.

PREREQUISITES:
- LANGSMITH_API_KEY: Your LangSmith API key
- LANGSMITH_WORKSPACE_ID: Your LangSmith workspace ID (found in workspace settings)
- GITHUB_INTEGRATION_ID: GitHub integration ID from LangSmith (one-time setup via UI)

ONE-TIME SETUP:
1. Go to LangSmith UI -> Deployments -> + New Deployment
2. Select "Import from GitHub" and complete the OAuth flow
3. Note your GitHub integration ID from LangSmith

Deployments use a stable canonical name of the form <service>-<env>, where
service defaults to [project].name from pyproject.toml (override with --name)
and env comes from --env (defaults to $APP_ENV, then "dev"). Re-running create
is an idempotent upsert: it updates the live deployment in place, or creates a
git-SHA rescue name only when the canonical name is stuck/orphaned.

CONTROL PLANE API REFERENCE:
    https://docs.langchain.com/langsmith/api-ref-control-plane
"""

# Click command callbacks expose one function parameter per CLI option, and the
# deployment-creation helper takes one per tunable deployment setting, so the
# argument count necessarily exceeds PLR0913's limit. Suppress it module-wide.
# ruff: noqa: PLR0913

from http import HTTPStatus
from pathlib import Path
from typing import Any

import click
import requests

from ess_langsmith_client import (
    ControlPlaneClient,
    choose_deploy_name,
    common_options,
    compute_base_name,
    create_client,
    echo_deployment_resolved,
    echo_success,
    env_option,
    get_git_sha,
    get_project_info,
    handle_wait,
    merge_secrets,
    print_deployments,
)
from ess_langsmith_client.client import _REQUEST_TIMEOUT


class GitHubDeploymentClient(ControlPlaneClient):
    """Client for GitHub-based deployments to LangSmith Cloud."""

    def create_deployment(
        self,
        name: str,
        integration_id: str,
        repo_url: str,
        branch: str = "main",
        config_path: str = "langgraph.json",
        deployment_type: str = "dev",
        build_on_push: bool = True,
        shareable: bool = False,
        secrets: list[dict[str, str]] | None = None,
        env_vars: list[dict[str, str]] | None = None,
        min_scale: int = 1,
        max_scale: int = 3,
        cpu: int = 1,
        memory_mb: int = 1024,
    ) -> dict[str, Any]:
        """Create a new deployment from a GitHub repository."""
        request_body = {
            "name": name,
            "source": "github",
            "source_config": {
                "integration_id": integration_id,
                "repo_url": repo_url,
                "deployment_type": deployment_type,
                "build_on_push": build_on_push,
                "custom_url": None,
                "resource_spec": {
                    "min_scale": min_scale,
                    "max_scale": max_scale,
                    "cpu": cpu,
                    "memory_mb": memory_mb,
                },
            },
            "source_revision_config": {
                "repo_ref": branch,
                "langgraph_config_path": config_path,
                "image_uri": None,
            },
            "secrets": secrets or [],
            "env_vars": env_vars or [],
            "shareable": shareable,
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
        branch: str | None = None,
        config_path: str | None = None,
        build_on_push: bool | None = None,
        secrets: list[dict[str, str]] | None = None,
        min_scale: int | None = None,
        max_scale: int | None = None,
        cpu: int | None = None,
        memory_mb: int | None = None,
    ) -> dict[str, Any]:
        """Update an existing GitHub deployment (creates a new revision).

        Applies secrets and the resource spec (when any of
        ``min_scale``/``max_scale``/``cpu``/``memory_mb`` is given) so
        re-deploying reconciles the full desired spec, not just branch/config.
        """
        request_body: dict[str, Any] = {}

        source_config: dict[str, Any] = {}
        if build_on_push is not None:
            source_config["build_on_push"] = build_on_push

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
            source_config["resource_spec"] = resource_spec

        if source_config:
            request_body["source_config"] = source_config

        if secrets:
            request_body["secrets"] = secrets

        source_revision_config: dict[str, Any] = {}
        if branch:
            source_revision_config["repo_ref"] = branch
        if config_path:
            source_revision_config["langgraph_config_path"] = config_path

        if source_revision_config:
            request_body["source_revision_config"] = source_revision_config

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
    """Deploy LangGraph agents to LangSmith from GitHub repositories.

    \b
    PREREQUISITES:
    - LANGSMITH_API_KEY: Your LangSmith API key
    - LANGSMITH_WORKSPACE_ID: Your workspace ID (from LangSmith settings)
    - GITHUB_INTEGRATION_ID: GitHub integration ID (one-time setup via UI)
    """
    pass


@cli.command()
@common_options
@env_option
@_project_dir_option
@click.option(
    "--name",
    help="Service name for the canonical <service>-<env> name "
    "(defaults to project name from pyproject.toml)",
)
@click.option("--repo-url", required=True, help="GitHub repository URL")
@click.option("--branch", default="main", help="Git branch to deploy from")
@click.option("--config-path", default="langgraph.json", help="Path to langgraph.json")
@click.option(
    "--integration-id", envvar="GITHUB_INTEGRATION_ID", help="GitHub integration ID"
)
@click.option(
    "--type",
    "deployment_type",
    type=click.Choice(["dev", "prod"]),
    default="dev",
    help="Deployment type",
)
@click.option("--auto-build/--no-auto-build", default=True, help="Auto rebuild on push")
@click.option("--shareable", is_flag=True, help="Make shareable via Studio")
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
    project_dir: str,
    name: str | None,
    repo_url: str,
    branch: str,
    config_path: str,
    integration_id: str | None,
    deployment_type: str,
    auto_build: bool,
    shareable: bool,
    secrets: tuple[str, ...],
    min_scale: int,
    max_scale: int,
    cpu: int,
    memory: int,
    wait: bool,
):
    """Deploy a GitHub repository to LangSmith (idempotent upsert).

    \b
    Resolves the canonical <service>-<env> name and:
    - updates the live deployment in place if one exists,
    - creates the canonical name if none exists,
    - creates a git-SHA rescue name (<service>-<env>-<sha>) only when the
      canonical name is stuck/orphaned.
    """
    if not integration_id:
        raise click.ClickException(
            "GitHub integration ID is required.\n"
            "Set GITHUB_INTEGRATION_ID env var or use --integration-id"
        )

    # Derive the service name from --name or pyproject.toml
    service = name
    if not service:
        project = get_project_info(start_path=Path(project_dir))
        if project:
            service = project.name
        else:
            raise click.ClickException(
                "Could not determine deployment name. "
                "Provide --name or ensure pyproject.toml exists with [project].name"
            )

    base = compute_base_name(service, env)

    client = create_client(GitHubDeploymentClient, api_key, workspace_id, region)

    try:
        live = client.resolve_live_deployment(base)

        if live:
            click.echo(f"Updating live deployment '{live['name']}' [{live['id']}]")
            click.echo(f"  Repository: {repo_url}")
            click.echo(f"  Branch: {branch}")
            click.echo(f"  Scale: {min_scale}-{max_scale} instances")
            result = client.update_deployment(
                deployment_id=live["id"],
                branch=branch,
                config_path=config_path,
                build_on_push=auto_build,
                secrets=merge_secrets(secrets),
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
        click.echo(f"Creating GitHub deployment: {deploy_name}")
        click.echo(f"  Repository: {repo_url}")
        click.echo(f"  Branch: {branch}")
        click.echo(f"  Scale: {min_scale}-{max_scale} instances")

        result = client.create_deployment(
            name=deploy_name,
            integration_id=integration_id,
            repo_url=repo_url,
            branch=branch,
            config_path=config_path,
            deployment_type=deployment_type,
            build_on_push=auto_build,
            shareable=shareable,
            secrets=merge_secrets(secrets),
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
@click.option("--deployment-id", required=True, help="Deployment ID to update")
@click.option("--branch", help="New branch to deploy from")
@click.option("--config-path", help="New config path")
@click.option(
    "--auto-build/--no-auto-build", default=None, help="Enable/disable auto-build"
)
@click.option("--wait", is_flag=True, help="Wait for deployment to complete")
def update(
    region: str,
    api_key: str | None,
    workspace_id: str | None,
    deployment_id: str,
    branch: str | None,
    config_path: str | None,
    auto_build: bool | None,
    wait: bool,
):
    """Update an existing deployment (creates a new revision)."""
    client = create_client(GitHubDeploymentClient, api_key, workspace_id, region)

    click.echo(f"Updating deployment: {deployment_id}")

    try:
        result = client.update_deployment(
            deployment_id=deployment_id,
            branch=branch,
            config_path=config_path,
            build_on_push=auto_build,
        )

        revision_id = result.get("latest_revision_id")
        click.echo(f"  New revision ID: {revision_id}")
        handle_wait(client, deployment_id, revision_id, wait)

    except RuntimeError as e:
        raise click.ClickException(str(e)) from e


@cli.command("list")
@common_options
@click.option("--filter", "name_filter", help="Filter by name (contains)")
@click.option("--github-only", is_flag=True, help="Show only GitHub deployments")
def list_deployments(
    region: str,
    api_key: str | None,
    workspace_id: str | None,
    name_filter: str | None,
    github_only: bool,
):
    """List deployments."""
    client = create_client(GitHubDeploymentClient, api_key, workspace_id, region)

    click.echo("Fetching deployments...")

    try:
        result = client.list_deployments(name_contains=name_filter)
        deployments = result.get("resources", [])

        if github_only:
            deployments = [
                deployment
                for deployment in deployments
                if deployment.get("source") == "github"
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
    client = create_client(GitHubDeploymentClient, api_key, workspace_id, region)

    click.echo(f"Deleting deployment: {deployment_id}")

    try:
        client.delete_deployment(deployment_id)
        echo_success("Deployment deleted successfully!")

    except RuntimeError as e:
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    cli()
