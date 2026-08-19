"""LangSmith Control Plane API client and CLI utilities.

This package provides a shared client for interacting with the
LangSmith Control Plane API.
"""

from ess_langsmith_client.cli import (
    common_options,
    create_client,
    deployment_option,
    echo_deployment_created,
    echo_deployment_resolved,
    echo_success,
    env_option,
    handle_wait,
    print_deployments,
    resolve_deployment_base_url,
    resolve_live_deployment_record,
)
from ess_langsmith_client.client import (
    CONTROL_PLANE_HOSTS,
    MAX_WAIT_TIME,
    POLL_INTERVAL,
    ControlPlaneClient,
)
from ess_langsmith_client.naming import (
    DEFAULT_ENV,
    ENV_VAR,
    choose_deploy_name,
    compute_base_name,
    get_git_sha,
    resolve_deploy_base,
    resolve_env,
    sanitize_name_component,
)
from ess_langsmith_client.project import (
    ProjectInfo,
    get_project_info,
)
from ess_langsmith_client.secrets import (
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
    "deployment_option",
    "echo_deployment_created",
    "echo_deployment_resolved",
    "echo_success",
    "env_option",
    "handle_wait",
    "print_deployments",
    "resolve_deployment_base_url",
    "resolve_live_deployment_record",
    # Secrets
    "get_env_secrets",
    "merge_secrets",
    "parse_secrets",
    # Project info
    "ProjectInfo",
    "get_project_info",
    # Naming convention
    "DEFAULT_ENV",
    "ENV_VAR",
    "choose_deploy_name",
    "compute_base_name",
    "get_git_sha",
    "resolve_deploy_base",
    "resolve_env",
    "sanitize_name_component",
]
