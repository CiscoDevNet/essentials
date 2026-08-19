#!/usr/bin/env python3
"""
Unified LangSmith Control Plane CLI.

Groups every LangSmith tool under a single ``langsmith-client`` command so you
do not have to remember individual entry points. Each subcommand is the same
Click group/command exposed by its module, composed here by reference.

USAGE:
    langsmith-client keys list
    langsmith-client workspaces list
    langsmith-client deploy docker create ...
    langsmith-client projects delete --name <name>

CONTROL PLANE API REFERENCE:
    https://docs.langchain.com/langsmith/api-ref-control-plane
"""

import click

from ess_langsmith_client._version import get_package_version
from ess_langsmith_client.agent_test.cli import deployed as test_deployed_cmd
from ess_langsmith_client.tools import (
    build,
    control_plane,
    deploy_docker,
    deploy_github,
    keys,
    list_listeners,
    list_workspaces,
    projects,
)


@click.group()
@click.version_option(version=get_package_version())
def cli() -> None:
    """LangSmith Control Plane CLI.

    \b
    PREREQUISITES:
    - LANGSMITH_API_KEY: Your LangSmith API key (admin for key/project ops)
    - LANGSMITH_WORKSPACE_ID: Your workspace ID (scopes tenant-specific calls)
    """


@cli.group()
def deploy() -> None:
    """Deploy agents from Docker images or GitHub repositories."""


cli.add_command(keys.cli, name="keys")
cli.add_command(list_workspaces.cli, name="workspaces")
cli.add_command(list_listeners.cli, name="listeners")
cli.add_command(projects.cli, name="projects")
cli.add_command(control_plane.cli, name="control-plane")
cli.add_command(build.build, name="build")
cli.add_command(test_deployed_cmd, name="test-deployed")

deploy.add_command(deploy_docker.cli, name="docker")
deploy.add_command(deploy_github.cli, name="github")


if __name__ == "__main__":
    cli()
