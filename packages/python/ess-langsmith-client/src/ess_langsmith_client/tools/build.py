#!/usr/bin/env python3
"""
Build a Docker image for a LangGraph agent.

Reads name and version from pyproject.toml to create a consistent image tag.
Can target any project directory via --project-dir / -C.
"""

# The build command callback exposes one function parameter per CLI option, so
# the argument count necessarily exceeds PLR0913's limit. Suppress it here.
# ruff: noqa: PLR0913

import os
import subprocess  # nosec B404  # developer tooling shells out to docker/langgraph
import sys
from pathlib import Path

import click

from ess_langsmith_client import get_git_sha, get_project_info


@click.command(
    context_settings={"ignore_unknown_options": True},
)
@click.option(
    "--tag", "-t", help="Override image tag (default: name:version from pyproject.toml)"
)
@click.option("--push", is_flag=True, help="Push to registry after build")
@click.option("--registry", help="Registry prefix for push (e.g., gcr.io/my-project)")
@click.option(
    "--platform",
    default="linux/amd64",
    help="Docker platform to build for (default: linux/amd64)",
)
@click.option(
    "--project-dir",
    "-C",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    default=".",
    help=(
        "Project directory containing pyproject.toml and langgraph.json "
        "(default: current directory)"
    ),
)
@click.argument("langgraph_args", nargs=-1, type=click.UNPROCESSED)
def build(
    tag: str | None,
    push: bool,
    registry: str | None,
    platform: str,
    project_dir: str,
    langgraph_args: tuple[str, ...],
):
    """Build a Docker image using langgraph build.

    Any additional arguments are passed to langgraph build.

    \b
    Examples:
        # Build with defaults from pyproject.toml
        langsmith-client build

        # Build a specific project
        langsmith-client build -C path/to/my-agent

        # Build with custom tag
        langsmith-client build -t my-image:v2

        # Build and push to registry
        langsmith-client build --push --registry gcr.io/my-project

        # Build for a different platform (e.g., local testing on Apple Silicon)
        langsmith-client build --platform linux/arm64
    """
    project_path = Path(project_dir)

    # Get tag from pyproject.toml if not provided
    if not tag:
        project = get_project_info(start_path=project_path)
        if not project:
            raise click.ClickException(
                "Could not read pyproject.toml. Provide --tag or ensure "
                "pyproject.toml exists."
            )
        git_sha = get_git_sha()
        tag = (
            f"{project.name}:{project.version}-{git_sha}"
            if git_sha
            else f"{project.name}:{project.version}"
        )

    click.echo(f"Building image: {tag}")
    click.echo(f"  Project dir: {project_path}")

    # Determine langgraph config path
    config_file = project_path / "langgraph.json"
    config_args = ["-c", str(config_file)] if config_file.exists() else []

    # Run langgraph build (--platform is passed through to docker build).
    # PYTHONUNBUFFERED ensures langgraph streams Docker output in real time.
    cmd = [
        "langgraph",
        "build",
        "-t",
        tag,
        *config_args,
        *langgraph_args,
        "--platform",
        platform,
    ]
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    result = subprocess.run(cmd, cwd=str(project_path), env=env, check=False)  # nosec B603 B607  # hardcoded langgraph command with list args, no shell

    if result.returncode != 0:
        sys.exit(result.returncode)

    click.echo(click.style(f"\nBuild complete: {tag}", fg="green"))

    # Push if requested
    if push:
        if registry:
            remote_tag = f"{registry}/{tag}"
            click.echo(f"\nTagging: {remote_tag}")
            subprocess.run(["docker", "tag", tag, remote_tag], check=True)  # nosec B603 B607  # hardcoded docker command with list args, no shell
            click.echo(f"Pushing: {remote_tag}")
            subprocess.run(["docker", "push", remote_tag], check=True)  # nosec B603 B607  # hardcoded docker command with list args, no shell
            click.echo(click.style(f"\nPushed: {remote_tag}", fg="green"))
        else:
            click.echo(f"Pushing: {tag}")
            subprocess.run(["docker", "push", tag], check=True)  # nosec B603 B607  # hardcoded docker command with list args, no shell
            click.echo(click.style(f"\nPushed: {tag}", fg="green"))


if __name__ == "__main__":
    build()  # pylint: disable=no-value-for-parameter  # Click injects params at runtime
