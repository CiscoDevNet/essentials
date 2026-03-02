"""Composable Azure AI stack deployment.

Provides ``deploy_stack()`` -- the single entry-point that orchestrates all
Azure OpenAI resources (account, model deployment, tag policies).  Callers can
extend the base firewall allow-list by passing ``extra_ips``.

Usage::

    from azure_ai.stack import deploy_stack

    # Standalone (base IPs only)
    result = deploy_stack()

    # With additional IPs (e.g. NAT Gateway from an EKS cluster)
    result = deploy_stack(extra_ips=["44.207.191.116"])
"""

from collections.abc import Sequence
from dataclasses import dataclass

import pulumi

from azure_ai.account import AccountOutputs, create_account
from azure_ai.config import AzureAIConfig, load_config
from azure_ai.deployment import DeploymentOutputs, create_deployment
from azure_ai.policy import create_tag_policies


@dataclass
class StackOutputs:
    """All outputs produced by a full Azure AI stack deployment."""

    account: AccountOutputs
    deployment: DeploymentOutputs
    config: AzureAIConfig


def deploy_stack(
    extra_ips: Sequence[str] = (),
) -> StackOutputs:
    """Deploy the full Azure AI stack and export Pulumi outputs.

    Args:
        extra_ips: Additional IP addresses or CIDR blocks to allow-list on
            the Cognitive Services firewall beyond the built-in LangSmith
            and Azure ranges.

    Returns:
        StackOutputs with account, deployment, and resolved config.
    """
    cfg = load_config()

    account = create_account(
        resource_group_name=cfg.resource_group_name,
        account_name=cfg.account_name,
        location=cfg.location,
        tags=cfg.tags,
        extra_ips=extra_ips,
    )

    deployment = create_deployment(
        deployment_name=cfg.deployment_name,
        resource_group_name=account.resource_group_name,
        account_name=account.account_name,
        endpoint=account.endpoint,
        model_name=cfg.model_name,
        model_version=cfg.model_version,
        api_version=cfg.api_version,
        capacity=cfg.capacity,
    )

    create_tag_policies(
        subscription_id=cfg.subscription_id,
        required_tags=list(cfg.tags.keys()),
    )

    _export_outputs(account, deployment, cfg)

    return StackOutputs(account=account, deployment=deployment, config=cfg)


def _export_outputs(
    account: AccountOutputs,
    deployment: DeploymentOutputs,
    cfg: AzureAIConfig,
) -> None:
    """Register standard Pulumi exports for the stack."""
    pulumi.export("resource_group_name", account.resource_group_name)
    pulumi.export("account_name", account.account_name)
    pulumi.export("deployment_name", deployment.deployment_name)
    pulumi.export("endpoint", account.endpoint)
    pulumi.export("primary_key", pulumi.Output.secret(account.primary_key))
    pulumi.export("secondary_key", pulumi.Output.secret(account.secondary_key))
    pulumi.export("allowed_ips", account.allowed_ips)
    pulumi.export("api_version", cfg.api_version)
    pulumi.export("usage_instructions", deployment.usage_instructions)
    pulumi.export("tags", cfg.tags)
