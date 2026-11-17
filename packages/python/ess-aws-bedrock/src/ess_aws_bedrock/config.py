"""Pulumi config loading for AWS Bedrock infrastructure.

Maps Pulumi stack configuration values (from Pulumi.<stack>.yaml) to typed
Python objects for use across resource modules.
"""

from dataclasses import dataclass, field

import pulumi
from pulumi_utils import get_resource_name

_DEFAULT_ENVIRONMENT = "development"
_DEFAULT_MODEL_PATTERNS = ("anthropic.*",)
_DEFAULT_BEDROCK_API_KEY_AGE_DAYS = 180
_MIN_BEDROCK_API_KEY_AGE_DAYS = 1
_MAX_BEDROCK_API_KEY_AGE_DAYS = 36600

MANAGED_BY = "pulumi"
_RESERVED_TAG_NAMESPACE = "aws:"


@dataclass(frozen=True)
class AwsBedrockConfig:
    """Typed configuration for the AWS Bedrock stack."""

    project_name: str
    region: str
    team_name: str
    environment: str
    user_name: str
    policy_name: str
    model_patterns: tuple[str, ...]
    create_access_key: bool = True
    create_bedrock_api_key: bool = False
    bedrock_api_key_age_days: int = _DEFAULT_BEDROCK_API_KEY_AGE_DAYS
    tags: dict[str, str] = field(default_factory=dict)


def _parse_model_patterns(raw: object) -> tuple[str, ...]:
    """Parse and validate the ``modelPatterns`` config value.

    Args:
        raw: Value from ``cfg.get_object("modelPatterns")``.
            ``None`` when the key is omitted. A bare string is
            accepted and wrapped into a single-element list.

    Returns:
        Validated tuple of non-empty model pattern strings.

    Raises:
        TypeError: If *raw* is not a list or contains non-string entries.
        ValueError: If the list is empty or contains only blank strings.
    """
    if raw is None:
        return _DEFAULT_MODEL_PATTERNS

    if isinstance(raw, str):
        raw = [raw]

    if not isinstance(raw, list):
        raise TypeError(
            f"modelPatterns must be a list of strings, got {type(raw).__name__}"
        )

    for entry in raw:
        if not isinstance(entry, str):
            raise TypeError(
                f"each entry in modelPatterns must be a string, "
                f"got {type(entry).__name__}: {entry!r}"
            )

    patterns = tuple(pattern.strip() for pattern in raw if pattern.strip())
    if not patterns:
        raise ValueError(
            "modelPatterns was set but contains no valid patterns; "
            "remove the key to use the defaults or provide at least one "
            f"non-empty pattern (defaults: {list(_DEFAULT_MODEL_PATTERNS)})"
        )

    return patterns


def _parse_bedrock_api_key_age_days(raw: int | None) -> int:
    """Validate the ``bedrockApiKeyAgeDays`` config value.

    Args:
        raw: Value from ``cfg.get_int("bedrockApiKeyAgeDays")``.
            ``None`` when the key is omitted.

    Returns:
        Number of days until the Bedrock API key expires.

    Raises:
        ValueError: If *raw* is outside the range IAM accepts.
    """
    if raw is None:
        return _DEFAULT_BEDROCK_API_KEY_AGE_DAYS

    if not _MIN_BEDROCK_API_KEY_AGE_DAYS <= raw <= _MAX_BEDROCK_API_KEY_AGE_DAYS:
        raise ValueError(
            f"bedrockApiKeyAgeDays must be between {_MIN_BEDROCK_API_KEY_AGE_DAYS} "
            f"and {_MAX_BEDROCK_API_KEY_AGE_DAYS}, got {raw}"
        )

    return raw


def _compose_tags(
    project_name: str,
    environment: str,
    tag_prefix: str | None,
) -> dict[str, str]:
    """Build the resource tags, namespacing each key when a prefix is given.

    Args:
        project_name: Value for the ``project`` tag.
        environment: Value for the ``environment`` tag.
        tag_prefix: Namespace for the tag keys, e.g. ``"myteam"`` produces
            ``myteam:project``. ``None`` or ``""`` leaves keys unprefixed.

    Returns:
        Tag keys mapped to their values.

    Raises:
        ValueError: If *tag_prefix* would produce a key in the ``aws:``
            namespace, which AWS reserves.
    """
    if tag_prefix and f"{tag_prefix}:".lower().startswith(_RESERVED_TAG_NAMESPACE):
        raise ValueError(
            f"tag_prefix {tag_prefix!r} produces keys in the reserved "
            f"{_RESERVED_TAG_NAMESPACE!r} namespace"
        )

    def compose_tag_key(name: str) -> str:
        return f"{tag_prefix}:{name}" if tag_prefix else name

    return {
        compose_tag_key("project"): project_name,
        compose_tag_key("managed-by"): MANAGED_BY,
        compose_tag_key("environment"): environment,
    }


def load_config(tag_prefix: str | None = None) -> AwsBedrockConfig:
    """Load and validate configuration from the Pulumi stack config.

    Args:
        tag_prefix: Namespace for the resource tag keys, e.g. ``"myteam"``
            produces ``myteam:project``. ``None`` leaves keys unprefixed.

    Raises:
        TypeError: If ``modelPatterns`` is not a ``str``, ``list[str]``,
            or contains non-string entries.
        ValueError: If ``modelPatterns`` is set but empty or all-blank,
            ``bedrockApiKeyAgeDays`` is outside 1-36600, or *tag_prefix*
            produces keys in the reserved ``aws:`` namespace.

    Returns:
        AwsBedrockConfig with all infrastructure parameters.
    """
    cfg = pulumi.Config()
    aws_cfg = pulumi.Config("aws")
    project_name = pulumi.get_project()
    team_name = cfg.require("teamName")
    environment = cfg.get("environment") or _DEFAULT_ENVIRONMENT
    region = aws_cfg.require("region")

    raw_patterns = cfg.get_object("modelPatterns")
    model_patterns = _parse_model_patterns(raw_patterns)

    return AwsBedrockConfig(
        project_name=project_name,
        region=region,
        team_name=team_name,
        environment=environment,
        user_name=cfg.get("userName")
        or get_resource_name(team_name, project_name, "bedrock"),
        policy_name=cfg.get("policyName")
        or get_resource_name(team_name, project_name, "bedrock-policy"),
        model_patterns=model_patterns,
        create_access_key=cfg.get_bool("createAccessKey", True),
        create_bedrock_api_key=cfg.get_bool("createBedrockApiKey", False),
        bedrock_api_key_age_days=_parse_bedrock_api_key_age_days(
            cfg.get_int("bedrockApiKeyAgeDays")
        ),
        tags=_compose_tags(project_name, environment, tag_prefix),
    )
