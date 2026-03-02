"""LangSmith Control Plane API client and CLI utilities.

This package provides the shared client for interacting with the
LangSmith Control Plane API.
"""

from langsmith_client.cli import (
    common_options,
    create_client,
    echo_deployment_created,
    echo_success,
    handle_wait,
    print_deployments,
)
from langsmith_client.client import (
    CONTROL_PLANE_HOSTS,
    MAX_WAIT_TIME,
    POLL_INTERVAL,
    ControlPlaneClient,
)
from langsmith_client.project import (
    ProjectInfo,
    get_project_info,
)
from langsmith_client.secrets import (
    get_env_secrets,
    merge_secrets,
    parse_secrets,
)

__all__ = [
    # Client
    "ControlPlaneClient",
    "CONTROL_PLANE_HOSTS",
    "MAX_WAIT_TIME",
    "POLL_INTERVAL",
    # CLI utilities
    "common_options",
    "create_client",
    "echo_deployment_created",
    "echo_success",
    "handle_wait",
    "print_deployments",
    # Secrets
    "get_env_secrets",
    "merge_secrets",
    "parse_secrets",
    # Project info
    "ProjectInfo",
    "get_project_info",
]
