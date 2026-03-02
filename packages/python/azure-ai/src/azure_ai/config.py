"""Pulumi config loading for Azure AI infrastructure.

Maps Pulumi stack configuration values (from Pulumi.<stack>.yaml) to typed
Python objects for use across resource modules.
"""

import os
from dataclasses import dataclass

import pulumi
from pulumi_utils import get_resource_name

_DEFAULT_LOCATION = "eastus2"
_DEFAULT_CAPACITY = 20
_DEFAULT_API_VERSION = "2025-01-01-preview"

MANAGED_BY = "pulumi"


@dataclass(frozen=True)
class AzureAIConfig:
    """Typed configuration for the Azure AI stack."""

    project_name: str
    location: str
    subscription_id: str
    resource_group_name: str
    account_name: str
    model_name: str
    deployment_name: str
    model_version: str | None
    api_version: str
    capacity: int
    environment: str
    tags: dict[str, str]


def load_config() -> AzureAIConfig:
    """Load and validate configuration from the Pulumi stack config.

    Returns:
        AzureAIConfig with all infrastructure parameters.
    """
    cfg = pulumi.Config()
    azure_cfg = pulumi.Config("azure-native")
    project_name = pulumi.get_project()
    team_name = cfg.require("teamName")
    model_name = cfg.get("modelName") or "gpt-chat"
    environment = cfg.get("environment") or "development"
    subscription_id = azure_cfg.require("subscriptionId")

    return AzureAIConfig(
        project_name=project_name,
        location=cfg.get("location") or _DEFAULT_LOCATION,
        subscription_id=subscription_id,
        resource_group_name=cfg.get("resourceGroupName")
        or get_resource_name(project_name, "openai-rg"),
        # Creates a Cognitive Services subdomain; must be globally unique.
        account_name=cfg.get("accountName")
        or get_resource_name(team_name, project_name, "openai"),
        model_name=model_name,
        deployment_name=cfg.get("deploymentName") or model_name,
        model_version=cfg.get("modelVersion"),
        api_version=(
            cfg.get("apiVersion")
            or os.environ.get("AZURE_OPENAI_API_VERSION")
            or _DEFAULT_API_VERSION
        ),
        capacity=cfg.get_int("capacity") or _DEFAULT_CAPACITY,
        environment=environment,
        tags={"managed-by": MANAGED_BY, "environment": environment},
    )
