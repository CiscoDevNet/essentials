# AWS Bedrock Anthropic Access

A Pulumi project that provisions IAM credentials for invoking Anthropic models on AWS Bedrock.

```python
from ess_aws_bedrock import deploy_stack

result = deploy_stack()
# result.iam.access_key_id, result.iam.secret_access_key, result.iam.bedrock_api_key
```

## What It Creates

- An IAM user scoped to Bedrock model invocation
- An inline IAM policy allowing `InvokeModel` on Anthropic foundation models
- A long-lived access key (access key ID + secret access key), unless `createAccessKey` is `false`
- A Bedrock API key (bearer token for `AWS_BEARER_TOKEN_BEDROCK`), when `createBedrockApiKey` is `true`

## Prerequisites

1. **AWS CLI** installed and configured with a profile that can create IAM users and policies
2. **Bedrock model access** -- serverless foundation models (including Anthropic Claude) are automatically enabled on first invocation. No manual approval is needed.
3. **Python 3.12+** and **Pulumi CLI** installed

## Setup

### 1. Install Dependencies

```bash
uv sync --all-packages
```

### 2. Authenticate to AWS

```bash
aws sso login --profile <profile>
aws sts get-caller-identity --profile <profile>
```

### 3. Configure Pulumi

```bash
cd packages/python/ess-aws-bedrock
cp Pulumi.example.yaml Pulumi.dev.yaml   # then replace YOUR_TEAM and your-aws-profile
uv run pulumi login file://.
uv run pulumi stack init dev
```

### 4. Deploy

```bash
uv run pulumi up
```

## Configuration

Set via `pulumi config set ess-aws-bedrock:<key> <value>`:

| Config Key | Description | Default |
| --- | --- | --- |
| `teamName` | Team identifier for resource naming (required). | _None_ (must be set) |
| `environment` | Environment tag. | `development` |
| `modelPatterns` | List of model ID patterns to allow. | `["anthropic.*"]` |
| `userName` | Override IAM user name. | `{team}-{project}-bedrock-{stack}` |
| `policyName` | Override IAM policy name. | `{team}-{project}-bedrock-policy-{stack}` |
| `createAccessKey` | Create a long-lived IAM access key. | `true` |
| `createBedrockApiKey` | Create a Bedrock API key and allow `bedrock:CallWithBearerToken`. | `false` |
| `bedrockApiKeyAgeDays` | Days until the Bedrock API key expires (1-36600). Some AWS organizations cap this with a service control policy; set it to match your limit. | `180` |

AWS provider config:

| Config Key | Description | Default |
| --- | --- | --- |
| `aws:region` | AWS region (required), e.g. `us-east-1`. | _None_ (must be set) |
| `aws:profile` | AWS SSO profile name. | _Inherited from AWS CLI config_ |

## Outputs

```bash
uv run pulumi stack output                                  # all outputs
uv run pulumi stack output access_key_id                    # access key ID
uv run pulumi stack output secret_access_key --show-secrets # secret key
uv run pulumi stack output bedrock_api_key --show-secrets   # Bedrock API key
uv run pulumi stack output usage_instructions               # Usage examples
```

- `user_name` -- IAM user name
- `user_arn` -- IAM user ARN
- `access_key_id` -- long-lived access key ID (when `createAccessKey` is on)
- `secret_access_key` -- (secret) long-lived secret access key (when `createAccessKey` is on)
- `bedrock_api_key` -- (secret) Bedrock API key (when `createBedrockApiKey` is on)
- `bedrock_api_key_alias` -- the API key's credential alias (`<user>-at-<account>`)
- `bedrock_api_key_expiration` -- when the API key expires
- `region` -- AWS region
- `allowed_models` -- model ID patterns allowed by the policy
- `usage_instructions` -- connection examples
- `tags` -- applied resource tags (`project`, `managed-by`, `environment`; prefixed when `tag_prefix` is set)

## Using Bedrock

### Python (anthropic SDK)

```python
import anthropic

client = anthropic.AnthropicBedrock(
    aws_access_key="YOUR_ACCESS_KEY_ID",
    aws_secret_key="YOUR_SECRET_ACCESS_KEY",
    aws_region="us-east-1",
)

message = client.messages.create(
    model="anthropic.claude-sonnet-4-20250514-v1:0",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello, Claude!"}],
)

print(message.content[0].text)
```

### Python (boto3)

```python
import json
import boto3

client = boto3.client(
    "bedrock-runtime",
    region_name="us-east-1",
    aws_access_key_id="YOUR_ACCESS_KEY_ID",
    aws_secret_access_key="YOUR_SECRET_ACCESS_KEY",
)

response = client.invoke_model(
    modelId="anthropic.claude-sonnet-4-20250514-v1:0",
    contentType="application/json",
    accept="application/json",
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "Hello, Claude!"}],
    }),
)

result = json.loads(response["body"].read())
print(result["content"][0]["text"])
```

### Environment Variables

```bash
export AWS_ACCESS_KEY_ID=$(uv run pulumi stack output access_key_id)
export AWS_SECRET_ACCESS_KEY=$(uv run pulumi stack output secret_access_key --show-secrets)
export AWS_DEFAULT_REGION=$(uv run pulumi stack output region)
```

### Claude Code (Bedrock API key)

```bash
export CLAUDE_CODE_USE_BEDROCK=1
export AWS_REGION=$(uv run pulumi stack output region)
export AWS_BEARER_TOKEN_BEDROCK=$(uv run pulumi stack output bedrock_api_key --show-secrets)
```

## Extending (Team-Specific Stacks)

Import `deploy_stack` from a team wrapper project and pass additional IAM policy statements. Pass `tag_prefix` to namespace the tag keys (`myteam:project` instead of `project`); by default they are unprefixed:

```python
from ess_aws_bedrock.stack import deploy_stack

deploy_stack(
    extra_statements=[{
        "Effect": "Allow",
        "Action": ["bedrock:Retrieve"],
        "Resource": "arn:aws:bedrock:us-east-1:123456789012:knowledge-base/*",
    }],
    tag_prefix="myteam",
)
```

## Destroying Resources

```bash
uv run pulumi destroy
```

This deletes the IAM user, policy, access key, and Bedrock API key. Any applications using the credentials will lose access immediately.

## Running Tests

```bash
uv run pytest packages/python/ess-aws-bedrock
```

Tests cover the policy document builder and config validation.

## License

[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/).
