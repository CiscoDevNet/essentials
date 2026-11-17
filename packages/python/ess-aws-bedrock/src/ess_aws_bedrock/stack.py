"""Composable AWS Bedrock stack deployment.

Provides ``deploy_stack()`` -- the single entry-point that orchestrates all
AWS Bedrock IAM resources (user, policy, access key, Bedrock API key).
Callers can extend the base policy by passing ``extra_statements``.

Usage::

    from ess_aws_bedrock.stack import deploy_stack

    # Standalone (Anthropic models only)
    result = deploy_stack()

    # With additional IAM policy statements
    result = deploy_stack(extra_statements=[{
        "Effect": "Allow",
        "Action": ["bedrock:Retrieve"],
        "Resource": "arn:aws:bedrock:us-east-1:123456789012:knowledge-base/*",
    }])
"""

from collections.abc import Sequence
from dataclasses import dataclass

import pulumi

from ess_aws_bedrock.config import AwsBedrockConfig, load_config
from ess_aws_bedrock.iam import IamOutputs, create_iam


@dataclass
class StackOutputs:
    """All outputs produced by a full AWS Bedrock stack deployment."""

    iam: IamOutputs
    config: AwsBedrockConfig


def deploy_stack(
    extra_statements: Sequence[dict] = (),
    *,
    tag_prefix: str | None = None,
) -> StackOutputs:
    """Deploy the full AWS Bedrock stack and export Pulumi outputs.

    Args:
        extra_statements: Additional IAM policy statements to merge into
            the Bedrock policy (e.g. for Knowledge Bases or Agents).
        tag_prefix: Namespace for resource tag keys (``<prefix>:project``,
            ``<prefix>:managed-by``, ``<prefix>:environment``). ``None``
            leaves keys unprefixed (``project``, ``managed-by``,
            ``environment``).

    Returns:
        StackOutputs with IAM credentials and resolved config.
    """
    cfg = load_config(tag_prefix=tag_prefix)

    iam = create_iam(
        user_name=cfg.user_name,
        policy_name=cfg.policy_name,
        model_patterns=cfg.model_patterns,
        tags=cfg.tags,
        extra_statements=extra_statements,
        create_access_key=cfg.create_access_key,
        create_bedrock_api_key=cfg.create_bedrock_api_key,
        bedrock_api_key_age_days=cfg.bedrock_api_key_age_days,
    )

    _export_outputs(iam, cfg)

    return StackOutputs(iam=iam, config=cfg)


def _build_usage_instructions(
    access_key_id: str,
    region: str,
) -> str:
    """Build usage instructions text for the provisioned Bedrock access.

    Args:
        access_key_id: The IAM access key ID (safe to display).
        region: AWS region for Bedrock API calls.

    Returns:
        Formatted usage instructions with credentials and Python examples.
    """
    return f"""
# AWS Bedrock Connection Information

## Credentials
Access Key ID: {access_key_id}
Secret Access Key: Use `pulumi stack output secret_access_key --show-secrets`
Region: {region}

## Python Usage (with anthropic SDK)
```python
import anthropic

client = anthropic.AnthropicBedrock(
    aws_access_key="YOUR_ACCESS_KEY_ID",
    aws_secret_key="YOUR_SECRET_ACCESS_KEY",
    aws_region="{region}",
)

message = client.messages.create(
    model="anthropic.claude-sonnet-4-20250514-v1:0",
    max_tokens=1024,
    messages=[
        {{"role": "user", "content": "Hello, Claude!"}}
    ],
)

print(message.content[0].text)
```

## Python Usage (with boto3)
```python
import json
import boto3

client = boto3.client(
    "bedrock-runtime",
    region_name="{region}",
    aws_access_key_id="YOUR_ACCESS_KEY_ID",
    aws_secret_access_key="YOUR_SECRET_ACCESS_KEY",
)

response = client.invoke_model(
    modelId="anthropic.claude-sonnet-4-20250514-v1:0",
    contentType="application/json",
    accept="application/json",
    body=json.dumps({{
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [
            {{"role": "user", "content": "Hello, Claude!"}}
        ],
    }}),
)

result = json.loads(response["body"].read())
print(result["content"][0]["text"])
```

## Environment Variables
export AWS_ACCESS_KEY_ID="{access_key_id}"
export AWS_SECRET_ACCESS_KEY="YOUR_SECRET_ACCESS_KEY"
export AWS_REGION="{region}"
export AWS_DEFAULT_REGION="{region}"  # Required by boto3

## Get Secret Access Key
Use: pulumi stack output secret_access_key --show-secrets
"""


def _build_api_key_usage_instructions(region: str) -> str:
    """Build usage instructions text for a Bedrock API key.

    Args:
        region: AWS region for Bedrock API calls.

    Returns:
        Formatted usage instructions for Claude Code and other bearer-token
        clients.
    """
    return f"""
# AWS Bedrock API Key

## Get the Key
Use: pulumi stack output bedrock_api_key --show-secrets
Expiry: pulumi stack output bedrock_api_key_expiration

## Claude Code
export CLAUDE_CODE_USE_BEDROCK=1
export AWS_REGION="{region}"
export AWS_BEARER_TOKEN_BEDROCK="YOUR_BEDROCK_API_KEY"
"""


def _export_outputs(iam: IamOutputs, cfg: AwsBedrockConfig) -> None:
    """Register standard Pulumi exports for the stack."""
    pulumi.export("user_name", iam.user_name)
    pulumi.export("user_arn", iam.user_arn)
    pulumi.export("region", cfg.region)
    pulumi.export("allowed_models", list(cfg.model_patterns))
    pulumi.export("tags", cfg.tags)

    instructions: list[pulumi.Input[str]] = []

    if iam.access_key_id is not None and iam.secret_access_key is not None:
        pulumi.export("access_key_id", iam.access_key_id)
        pulumi.export("secret_access_key", pulumi.Output.secret(iam.secret_access_key))
        instructions.append(
            iam.access_key_id.apply(
                lambda key_id: _build_usage_instructions(key_id, cfg.region)
            )
        )

    if iam.bedrock_api_key is not None:
        pulumi.export("bedrock_api_key", iam.bedrock_api_key)
        pulumi.export("bedrock_api_key_alias", iam.bedrock_api_key_alias)
        pulumi.export("bedrock_api_key_expiration", iam.bedrock_api_key_expiration)
        instructions.append(_build_api_key_usage_instructions(cfg.region))

    if instructions:
        pulumi.export(
            "usage_instructions",
            pulumi.Output.all(*instructions).apply("".join),
        )
