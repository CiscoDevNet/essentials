"""AWS IAM resources for Bedrock model access.

Creates an IAM user with a scoped policy for invoking Bedrock foundation
models, plus optional credentials: a long-lived access key for SigV4 API
access and/or a Bedrock API key (bearer token) for tools such as Claude Code.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass

import pulumi
import pulumi_aws as aws

_BEDROCK_SERVICE_NAME = "bedrock.amazonaws.com"


@dataclass
class IamOutputs:
    """Outputs from the IAM module.

    Credential fields are ``None`` when the corresponding credential is
    disabled in config.
    """

    user_name: pulumi.Output[str]
    user_arn: pulumi.Output[str]
    access_key_id: pulumi.Output[str] | None = None
    secret_access_key: pulumi.Output[str] | None = None
    bedrock_api_key: pulumi.Output[str] | None = None
    bedrock_api_key_alias: pulumi.Output[str] | None = None
    bedrock_api_key_expiration: pulumi.Output[str] | None = None


def _build_model_resources(
    model_patterns: Sequence[str],
) -> list[str]:
    """Build IAM policy resource ARNs from model ID patterns.

    Args:
        model_patterns: Model ID patterns (e.g. ``["anthropic.*"]``).

    Returns:
        List of ARN strings with wildcard region for each pattern.
    """
    return [
        f"arn:aws:bedrock:*::foundation-model/{pattern}" for pattern in model_patterns
    ]


def _build_policy_document(
    model_patterns: Sequence[str],
    extra_statements: Sequence[dict] = (),
    allow_bearer_token: bool = False,
) -> str:
    """Build the IAM policy JSON document for Bedrock access.

    Args:
        model_patterns: Model ID patterns to allow invocation on.
        extra_statements: Additional IAM policy statements to include.
            Must be plain Python dicts — Pulumi ``Output`` values inside
            statements will cause ``json.dumps()`` to fail.
        allow_bearer_token: Grant ``bedrock:CallWithBearerToken``, which
            Bedrock requires before it accepts a Bedrock API key.

    Returns:
        JSON-encoded IAM policy document.
    """
    statements: list[dict] = [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
            ],
            "Resource": _build_model_resources(model_patterns),
        },
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
            ],
            "Resource": "arn:aws:bedrock:*:*:inference-profile/us.*",
        },
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:ListFoundationModels",
                "bedrock:GetFoundationModel",
                "bedrock:ListInferenceProfiles",
            ],
            "Resource": "*",
        },
    ]
    if allow_bearer_token:
        statements.append(
            {
                "Effect": "Allow",
                "Action": "bedrock:CallWithBearerToken",
                "Resource": "*",
            }
        )
    statements.extend(extra_statements)

    return json.dumps({"Version": "2012-10-17", "Statement": statements})


def create_iam(  # noqa: PLR0913
    user_name: str,
    policy_name: str,
    model_patterns: Sequence[str],
    tags: dict[str, str],
    extra_statements: Sequence[dict] = (),
    *,
    create_access_key: bool = True,
    create_bedrock_api_key: bool = False,
    bedrock_api_key_age_days: int | None = None,
) -> IamOutputs:
    """Create an IAM user with Bedrock invoke permissions and credentials.

    Args:
        user_name: Name for the IAM user.
        policy_name: Name for the inline IAM policy.
        model_patterns: Model ID patterns to allow (e.g. ``["anthropic.*"]``).
        tags: AWS resource tags to apply.
        extra_statements: Additional IAM policy statements to merge into the
            policy document (e.g. for Bedrock Knowledge Bases or Agents).
            Must be plain Python dicts — Pulumi ``Output`` values inside
            statements will cause ``json.dumps()`` to fail.
        create_access_key: Create a long-lived IAM access key.
        create_bedrock_api_key: Create a Bedrock API key (service-specific
            credential) and allow ``bedrock:CallWithBearerToken``.
        bedrock_api_key_age_days: Days until the Bedrock API key expires.
            ``None`` creates a key that never expires.

    Returns:
        IamOutputs with user identifiers and the enabled credentials.
    """
    user = aws.iam.User(
        "bedrock-user",
        name=user_name,
        tags=tags,
    )

    aws.iam.UserPolicy(
        "bedrock-policy",
        user=user.name,
        name=policy_name,
        policy=_build_policy_document(
            model_patterns,
            extra_statements,
            allow_bearer_token=create_bedrock_api_key,
        ),
    )

    outputs = IamOutputs(user_name=user.name, user_arn=user.arn)

    if create_access_key:
        access_key = aws.iam.AccessKey(
            "bedrock-access-key",
            user=user.name,
        )
        outputs.access_key_id = access_key.id
        outputs.secret_access_key = access_key.secret

    if create_bedrock_api_key:
        credential = aws.iam.ServiceSpecificCredential(
            "bedrock-api-key",
            service_name=_BEDROCK_SERVICE_NAME,
            user_name=user.name,
            credential_age_days=bedrock_api_key_age_days,
        )
        # For Bedrock, the secret is already the complete ABSK... API key.
        outputs.bedrock_api_key = pulumi.Output.secret(
            credential.service_credential_secret
        )
        outputs.bedrock_api_key_alias = credential.service_credential_alias
        outputs.bedrock_api_key_expiration = credential.expiration_date

    return outputs
