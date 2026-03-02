"""Azure OpenAI model deployment resources.

Creates a GPT model deployment on an existing Cognitive Services account
and generates usage instructions for the deployed endpoint.
"""

from dataclasses import dataclass

import pulumi
import pulumi_azure_native as azure_native
from pulumi import Output


@dataclass
class DeploymentOutputs:
    """Outputs from the model deployment module."""

    deployment_name: pulumi.Output[str]
    usage_instructions: pulumi.Output[str]


def _get_curl_url(endpoint: str, deployment: str, api_version: str) -> str:
    """Generate a cURL URL for Azure OpenAI chat completions.

    Args:
        endpoint: The Azure OpenAI endpoint URL.
        deployment: The deployment name.
        api_version: The API version string.

    Returns:
        The full cURL URL with API version parameter.
    """
    return (
        f"{endpoint}/openai/deployments/{deployment}/"
        f"chat/completions?api-version={api_version}"
    )


def _build_usage_instructions(
    endpoint: str,
    deployment_name: str,
    api_version: str,
) -> str:
    """Build usage instructions text for the deployed model.

    Args:
        endpoint: The Azure OpenAI endpoint URL.
        deployment_name: The deployment name.
        api_version: The API version string.

    Returns:
        Formatted usage instructions with Python and cURL examples.
    """
    curl_url = _get_curl_url(endpoint, deployment_name, api_version)

    return f"""
# Azure OpenAI Connection Information

## API Endpoint
{endpoint}

## Deployment Name
{deployment_name}

## Python Usage (with openai SDK)
```python
import os
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version="{api_version}",
    azure_endpoint="{endpoint}"
)

response = client.chat.completions.create(
    model="{deployment_name}",  # Use deployment name, not model name
    messages=[
        {{"role": "system", "content": "You are a helpful assistant."}},
        {{"role": "user", "content": "Hello!"}}
    ]
)

print(response.choices[0].message.content)
```

## cURL Example
```bash
curl "{curl_url}" \\
  -H "Content-Type: application/json" \\
  -H "api-key: $AZURE_OPENAI_API_KEY" \\
  -d '{{
    "messages": [
      {{"role": "system", "content": "You are a helpful assistant."}},
      {{"role": "user", "content": "Hello!"}}
    ]
  }}'
```

## Environment Variables
export AZURE_OPENAI_ENDPOINT="{endpoint}"
export AZURE_OPENAI_API_KEY="YOUR_API_KEY"
export AZURE_OPENAI_DEPLOYMENT_NAME="{deployment_name}"

## Get API Key
Use: pulumi stack output primary_key --show-secrets
"""


def create_deployment(  # noqa: PLR0913
    deployment_name: str,
    resource_group_name: pulumi.Output[str],
    account_name: pulumi.Output[str],
    endpoint: pulumi.Output[str],
    model_name: str,
    model_version: str | None,
    api_version: str,
    capacity: int,
) -> DeploymentOutputs:
    """Create a GPT model deployment on an Azure OpenAI account.

    Args:
        deployment_name: Name for the model deployment.
        resource_group_name: Resource group containing the account.
        account_name: Cognitive Services account name.
        endpoint: The Azure OpenAI endpoint URL.
        model_name: OpenAI model name (e.g. "gpt-chat").
        model_version: Model version, or None for latest.
        api_version: Azure OpenAI REST API version (e.g. "2025-01-01-preview").
            Independent of model_version — see:
            https://learn.microsoft.com/azure/ai-services/openai/api-version-deprecation
        capacity: Deployment capacity in thousands of tokens per minute.

    Returns:
        DeploymentOutputs with deployment name and usage instructions.
    """
    model_args: dict[str, str] = {
        "format": "OpenAI",
        "name": model_name,
    }
    if model_version:
        model_args["version"] = model_version

    model_deployment = azure_native.cognitiveservices.Deployment(
        deployment_name,
        deployment_name=deployment_name,
        resource_group_name=resource_group_name,
        account_name=account_name,
        properties=azure_native.cognitiveservices.DeploymentPropertiesArgs(
            model=azure_native.cognitiveservices.DeploymentModelArgs(**model_args),
        ),
        sku=azure_native.cognitiveservices.SkuArgs(
            name="GlobalStandard",
            capacity=capacity,
        ),
    )

    usage_instructions = Output.all(
        endpoint,
        model_deployment.name,
    ).apply(
        lambda args: _build_usage_instructions(
            endpoint=args[0],
            deployment_name=args[1],
            api_version=api_version,
        )
    )

    return DeploymentOutputs(
        deployment_name=model_deployment.name,
        usage_instructions=usage_instructions,
    )
