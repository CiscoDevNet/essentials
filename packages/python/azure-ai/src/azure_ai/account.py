"""Azure OpenAI account and resource group resources.

Creates the resource group, Cognitive Services account with network ACLs,
and retrieves the API keys.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import pulumi
import pulumi_azure_native as azure_native

# LangSmith Cloud NAT gateway IPs.
# Source: https://docs.langchain.com/langsmith/deploy-to-cloud#allowlist-ip-addresses
LANGSMITH_IPS: tuple[str, ...] = (
    "34.9.99.224",
    "34.19.34.50",
    "34.19.93.202",
    "34.31.121.70",
    "34.41.178.137",
    "34.59.244.194",
    "34.68.27.146",
    "34.82.222.17",
    "34.121.166.52",
    "34.123.151.210",
    "34.135.61.140",
    "34.145.102.123",
    "34.169.45.153",
    "34.169.88.30",
    "35.197.29.146",
    "35.227.171.135",
    "34.13.244.114",
    "34.32.141.108",
    "34.32.145.240",
    "34.32.180.189",
    "34.34.69.108",
    "34.90.157.44",
    "34.90.213.236",
    "34.141.242.180",
)

AZURE_IPS: tuple[str, ...] = ("172.203.0.0/16",)


@dataclass
class AccountOutputs:
    """Outputs from the OpenAI account module."""

    resource_group_name: pulumi.Output[str]
    account_name: pulumi.Output[str]
    endpoint: pulumi.Output[str]
    primary_key: pulumi.Output[str]
    secondary_key: pulumi.Output[str]
    allowed_ips: pulumi.Output[list[str]]


def create_account(
    resource_group_name: str,
    account_name: str,
    location: str,
    tags: dict[str, str],
    extra_ips: Sequence[str] = (),
) -> AccountOutputs:
    """Create the Azure resource group and OpenAI Cognitive Services account.

    Args:
        resource_group_name: Name for the Azure resource group.
        account_name: Name for the OpenAI Cognitive Services account.
        location: Azure region (e.g. "eastus2").
        tags: Azure resource tags to apply.
        extra_ips: Additional IP addresses or CIDR blocks to allow-list
            (e.g. NAT Gateway IPs from an AWS EKS cluster).

    Returns:
        AccountOutputs with resource identifiers, endpoint, and API keys.
    """
    ip_rules = [
        azure_native.cognitiveservices.IpRuleArgs(value=ip)
        for ip in LANGSMITH_IPS + AZURE_IPS + tuple(extra_ips)
    ]

    network_acls = azure_native.cognitiveservices.NetworkRuleSetArgs(
        default_action="Deny",
        ip_rules=ip_rules,
    )

    resource_group = azure_native.resources.ResourceGroup(
        "openai-resource-group",
        resource_group_name=resource_group_name,
        location=location,
        tags=tags,
    )

    openai_account = azure_native.cognitiveservices.Account(
        "openai-account",
        account_name=account_name,
        resource_group_name=resource_group.name,
        location=location,
        kind="OpenAI",
        sku=azure_native.cognitiveservices.SkuArgs(
            name="S0",
        ),
        properties=azure_native.cognitiveservices.AccountPropertiesArgs(
            custom_sub_domain_name=account_name,
            public_network_access="Enabled",
            network_acls=network_acls,
        ),
        tags=tags,
    )

    account_keys = pulumi.Output.all(
        resource_group.name,
        openai_account.name,
    ).apply(
        lambda args: azure_native.cognitiveservices.list_account_keys(
            resource_group_name=args[0],
            account_name=args[1],
        )
    )

    allowed_ips_output = openai_account.properties.apply(
        lambda props: (
            [
                rule.value
                for rule in (props.network_acls.ip_rules or [])
                if props.network_acls and props.network_acls.ip_rules
            ]
            if props.network_acls
            else []
        )
    )

    return AccountOutputs(
        resource_group_name=resource_group.name,
        account_name=openai_account.name,
        endpoint=openai_account.properties.endpoint,
        primary_key=account_keys.key1,
        secondary_key=account_keys.key2,
        allowed_ips=allowed_ips_output,
    )
