# Azure OpenAI GPT-5

A Pulumi project that provisions Azure OpenAI services with GPT-5 model deployment for API-based access.

## Overview

This project creates:

- An Azure Resource Group for OpenAI resources
- An Azure OpenAI Cognitive Services Account
- A GPT-5 model deployment with configurable capacity
- API keys for secure authentication
- Connection endpoints and usage instructions

## Prerequisites

- Azure subscription with OpenAI access (may require approval)
- Azure CLI installed and logged in (`az login`)
- Python 3.12 or later
- Pulumi CLI installed
- Poetry (for package management)

## Setup

### 1. Install Dependencies

```bash
# From the essentials root
uv sync --all-packages
```

### 2. Login to Azure

```bash
# Login to Azure
az login

# Set your subscription (if you have multiple)
az account set --subscription "YOUR_SUBSCRIPTION_ID"
```

### 3. Configure Pulumi

```bash
# Login to Pulumi (if not already done)
pulumi login

# Set up the stack
pulumi stack init dev
```

### 4. Deploy

```bash
pulumi up
```

## Configuration

The project supports configuration via Pulumi config:

### Basic Configuration

| Variable            | Default               | Description                       |
| ------------------- | --------------------- | --------------------------------- |
| `location`          | `eastus`              | Azure region for resources        |
| `resourceGroupName` | `{project}-openai-rg` | Name of the resource group        |
| `accountName`       | `{project}-openai`    | Name of the OpenAI account        |
| `deploymentName`    | `{project}-gpt5chat`  | Name of the model deployment      |
| `modelName`         | `gpt-5-chat`          | Model to deploy                   |
| `modelVersion`      | _(latest)_            | Specific model version (optional) |
| `capacity`          | `10`                  | Capacity in thousands of TPM      |
| `allowedIpStart`    | _(optional)_          | Start IP for allowed range        |
| `allowedIpEnd`      | _(optional)_          | End IP for allowed range          |

### Setting Configuration Values

```bash
# Optional: Customize account name
pulumi config set accountName my-app-openai

# Optional: Set specific model version
pulumi config set modelVersion "2025-08-07"

# Optional: Increase capacity for production
pulumi config set capacity 80

# Optional: Restrict access to specific IP range
pulumi config set allowedIpStart "203.0.113.0"
pulumi config set allowedIpEnd "203.0.113.255"
```

## Model and Capacity Planning

### Available Models

According to [Azure OpenAI documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/overview), available models include:

- gpt-5 series (latest)
- o4-mini & o3
- gpt-4.1
- o3-mini & o1
- GPT-4o & GPT-4o mini
- GPT-4 series
- GPT-3.5-Turbo series

### Capacity (Tokens Per Minute)

Capacity is measured in thousands of tokens per minute (TPM):

| Capacity | TPM     | Use Case            | Estimated Cost Impact |
| -------- | ------- | ------------------- | --------------------- |
| 10       | 10,000  | Dev/Testing         | Minimal               |
| 30       | 30,000  | Small production    | Low                   |
| 80       | 80,000  | Standard production | Medium                |
| 240      | 240,000 | High-volume         | High                  |

### Regional Availability

GPT-5 availability varies by region. Recommended regions:

- `eastus` (East US)
- `eastus2` (East US 2)
- `swedencentral` (Sweden Central)
- `northcentralus` (North Central US)

Check the [Azure OpenAI model availability page](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models) for the latest information.

## Using Azure OpenAI

After deployment, retrieve connection information:

```bash
# View all outputs
pulumi stack output

# View endpoint
pulumi stack output endpoint

# View API key (secure)
pulumi stack output primary_key --show-secrets

# View usage instructions
pulumi stack output usage_instructions
```

### Python Example

```python
import os
from openai import AzureOpenAI

# Get these from Pulumi outputs
client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version="2024-08-01-preview",
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"]
)

response = client.chat.completions.create(
    model=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is Azure OpenAI?"}
    ]
)

print(response.choices[0].message.content)
```

### Environment Variables Setup

```bash
# Export connection details
export AZURE_OPENAI_ENDPOINT=$(pulumi stack output endpoint)
export AZURE_OPENAI_API_KEY=$(pulumi stack output primary_key --show-secrets)
export AZURE_OPENAI_DEPLOYMENT_NAME=$(pulumi stack output deployment_name)
```

### cURL Example

```bash
curl "$AZURE_OPENAI_ENDPOINT/openai/deployments/$AZURE_OPENAI_DEPLOYMENT_NAME/chat/completions?api-version=2024-08-01-preview" \
  -H "Content-Type: application/json" \
  -H "api-key: $AZURE_OPENAI_API_KEY" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

### JavaScript/TypeScript Example

```typescript
import { AzureOpenAI } from "openai";

const client = new AzureOpenAI({
  apiKey: process.env.AZURE_OPENAI_API_KEY,
  apiVersion: "2024-08-01-preview",
  endpoint: process.env.AZURE_OPENAI_ENDPOINT,
});

const response = await client.chat.completions.create({
  model: process.env.AZURE_OPENAI_DEPLOYMENT_NAME!,
  messages: [
    { role: "system", content: "You are a helpful assistant." },
    { role: "user", content: "Hello!" },
  ],
});

console.log(response.choices[0].message.content);
```

## Security Best Practices

### 1. API Key Management

- **Never commit API keys to version control**
- Store keys in environment variables or Azure Key Vault
- Rotate keys regularly using the secondary key for zero-downtime rotation
- Use the secondary key during rotation:
  ```bash
  pulumi stack output secondary_key --show-secrets
  ```

### 2. Network Security

#### IP-Based Restrictions (Recommended for Production)

Restrict access to specific IP addresses or CIDR blocks:

```bash
# Restrict to a single IP address
pulumi config set allowedIps "203.0.113.42"

# Allow a CIDR block (subnet)
pulumi config set allowedIps "203.0.113.0/24"

# Allow multiple IPs and/or CIDR blocks (comma-separated)
pulumi config set allowedIps "203.0.113.42, 192.168.1.0/24, 10.0.0.1"

pulumi up
```

**When IP restrictions are configured:**

- The default action is `Deny` (blocks all IPs)
- Only the specified IP addresses and CIDR blocks can access the API
- Supports both single IPs (e.g., `"203.0.113.42"`) and CIDR notation (e.g., `"203.0.113.0/24"`)
- Multiple IPs/CIDRs can be specified as a comma-separated list
- API key is still required for authentication

**Without IP restrictions:**

- Public network access is enabled
- Any IP can access (with valid API key)
- Suitable for development, but consider restrictions for production

#### Additional Network Security Options

For production environments:

- Consider using Azure Private Link for private connectivity
- Use Azure Virtual Networks (VNet) for isolation
- Implement Azure Front Door or Application Gateway for additional protection

### 3. Cost Management

- Set appropriate TPM capacity limits
- Monitor usage in Azure Portal
- Set up cost alerts
- Use quotas to prevent unexpected charges

### 4. Content Filtering

Azure OpenAI includes built-in content filtering:

- Prompts and completions are evaluated against content policies
- High severity content is automatically filtered
- Configure custom content filters in Azure Portal if needed

## Cost Estimation

Pricing varies by model and region. As of 2025, approximate costs for GPT-5:

- **Prompt tokens**: Variable per 1M tokens
- **Completion tokens**: Variable per 1M tokens
- **Capacity reservation**: Based on provisioned TPM

Check [Azure OpenAI Pricing](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/) for current rates.

### Example Monthly Costs

Development/Testing (10K TPM, light usage):

- Estimated: $10-50/month

Standard Production (80K TPM, moderate usage):

- Estimated: $200-1000/month

High Volume (240K TPM, heavy usage):

- Estimated: $1000+/month

## Project Structure

```
packages/python/azure-ai/
├── pyproject.toml        # Dependencies
├── Pulumi.yaml           # Pulumi project config
├── README.md             # This file
├── docs/                 # Guides
└── src/
    └── azure_ai/
        ├── __init__.py
        ├── __main__.py   # Standalone entry-point
        ├── account.py    # Resource group + Cognitive Services account
        ├── config.py     # Typed Pulumi config loader
        ├── deployment.py # GPT model deployment
        ├── policy.py     # Tag-enforcement policies
        └── stack.py      # Composable stack orchestrator
```

## Outputs

After deployment, the following outputs are available:

- `resource_group_name`: Name of the created resource group
- `account_name`: Name of the Azure OpenAI account
- `deployment_name`: Name of the model deployment
- `endpoint`: API endpoint URL
- `primary_key`: Primary API key (secret)
- `secondary_key`: Secondary API key (secret)
- `usage_instructions`: Detailed connection and usage examples

## Troubleshooting

### Cannot Access Azure OpenAI

Azure OpenAI requires approval for access:

1. Apply for access: https://aka.ms/oai/access
2. Wait for approval email (may take several days)
3. Ensure your subscription has the `Microsoft.CognitiveServices` resource provider registered

```bash
az provider register --namespace Microsoft.CognitiveServices
```

### Model Not Available in Region

1. Check model availability in your region
2. Try a different region (eastus, eastus2, swedencentral)
3. Update configuration:
   ```bash
   pulumi config set location eastus2
   pulumi up
   ```

### Rate Limiting (429 Errors)

1. Your capacity (TPM) may be too low for your usage
2. Increase capacity:
   ```bash
   pulumi config set capacity 30
   pulumi up
   ```
3. Implement retry logic with exponential backoff in your application

### Authentication Errors

1. Verify API key:
   ```bash
   pulumi stack output primary_key --show-secrets
   ```
2. Ensure you're using the correct endpoint
3. Check that your API key hasn't been rotated

### Deployment Quota Exceeded

Azure OpenAI has regional quotas:

1. Request a quota increase in Azure Portal
2. Try deploying in a different region
3. Delete unused deployments to free up quota

## Destroying Resources

To remove all resources:

```bash
pulumi destroy
```

This will delete:

- The model deployment
- The Azure OpenAI account
- The resource group (and all contained resources)

**Warning**: This action is irreversible. Ensure you have backups of any important data.

### Important: Protected Resources

If your resources were **imported** into Pulumi (rather than created fresh), they are automatically protected to prevent accidental deletion. You must remove the protect flag before destroying them.

**For detailed instructions**, see: [Destroying Resources Guide](docs/destroying-resources.md)

Quick steps:

1. Remove protection: `pulumi state unprotect --all` (or update code to set `protect=False`)
2. Apply changes: `pulumi up`
3. Destroy resources: `pulumi destroy`

## Getting Help

- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/overview)
- [Pulumi Azure Native Provider](https://www.pulumi.com/registry/packages/azure-native/)
- [OpenAI Python SDK Documentation](https://github.com/openai/openai-python)
- [Azure OpenAI Service REST API Reference](https://learn.microsoft.com/en-us/azure/ai-services/openai/reference)

## Next Steps

Consider:

- Implementing rate limiting and retry logic in your application
- Setting up monitoring and logging
- Creating multiple deployments for different models
- Integrating with Azure Key Vault for secrets management
- Adding custom content filtering policies
- Setting up Azure Monitor alerts for usage and errors
