"""Pulumi config loading for LangSmith Hosting infrastructure.

Maps Pulumi stack configuration values (from Pulumi.<stack>.yaml) to typed
Python objects, mirroring the Terraform variables.tf definitions.

All defaults below are validated against the Terraform dev.tfvars reference.
Override any value by adding the corresponding key to your Pulumi.<stack>.yaml.
"""

import os
from dataclasses import dataclass

import pulumi

# =============================================================================
# Sensible defaults — override via Pulumi stack config when needed
# =============================================================================

_VPC_CIDR = "10.0.0.0/16"

_EKS_CLUSTER_VERSION = "1.31"
_EKS_NODE_INSTANCE_TYPE = "m5.xlarge"
_EKS_NODE_MIN_SIZE = 2
_EKS_NODE_MAX_SIZE = 5
_EKS_NODE_DESIRED_SIZE = 2

_POSTGRES_INSTANCE_CLASS = "db.t3.medium"
_POSTGRES_ENGINE_VERSION = "16.6"
_POSTGRES_ALLOCATED_STORAGE = 20
_POSTGRES_MAX_ALLOCATED_STORAGE = 100

_REDIS_NODE_TYPE = "cache.t3.micro"

_S3_BUCKET_PREFIX = "langsmith"

_AWS_PROFILE = os.environ.get("AWS_PROFILE", "")


@dataclass(frozen=True)
class LangSmithConfig:
    """Typed configuration for the LangSmith Hosting stack."""

    # General
    environment: str

    # VPC
    vpc_cidr: str

    # EKS
    eks_cluster_name: str
    eks_cluster_version: str
    eks_node_instance_type: str
    eks_node_min_size: int
    eks_node_max_size: int
    eks_node_desired_size: int

    # PostgreSQL (RDS)
    postgres_instance_class: str
    postgres_engine_version: str
    postgres_allocated_storage: int
    postgres_max_allocated_storage: int

    # Redis (ElastiCache)
    redis_node_type: str

    # S3
    s3_bucket_prefix: str

    # LangSmith Control Plane
    langsmith_api_key: pulumi.Output[str]
    langsmith_workspace_id: str

    # AWS
    aws_profile: str


def load_config() -> LangSmithConfig:
    """Load and validate all configuration values from the Pulumi stack config.

    Returns:
        LangSmithConfig with all infrastructure parameters.
    """
    cfg = pulumi.Config()

    return LangSmithConfig(
        # General
        environment=cfg.require("environment"),
        # VPC
        vpc_cidr=cfg.get("vpcCidr") or _VPC_CIDR,
        # EKS
        eks_cluster_name=cfg.require("eksClusterName"),
        eks_cluster_version=cfg.get("eksClusterVersion") or _EKS_CLUSTER_VERSION,
        eks_node_instance_type=cfg.get("eksNodeInstanceType")
        or _EKS_NODE_INSTANCE_TYPE,
        eks_node_min_size=cfg.get_int("eksNodeMinSize") or _EKS_NODE_MIN_SIZE,
        eks_node_max_size=cfg.get_int("eksNodeMaxSize") or _EKS_NODE_MAX_SIZE,
        eks_node_desired_size=cfg.get_int("eksNodeDesiredSize")
        or _EKS_NODE_DESIRED_SIZE,
        # PostgreSQL
        postgres_instance_class=cfg.get("postgresInstanceClass")
        or _POSTGRES_INSTANCE_CLASS,
        postgres_engine_version=cfg.get("postgresEngineVersion")
        or _POSTGRES_ENGINE_VERSION,
        postgres_allocated_storage=cfg.get_int("postgresAllocatedStorage")
        or _POSTGRES_ALLOCATED_STORAGE,
        postgres_max_allocated_storage=cfg.get_int("postgresMaxAllocatedStorage")
        or _POSTGRES_MAX_ALLOCATED_STORAGE,
        # Redis
        redis_node_type=cfg.get("redisNodeType") or _REDIS_NODE_TYPE,
        # S3
        s3_bucket_prefix=cfg.get("s3BucketPrefix") or _S3_BUCKET_PREFIX,
        # LangSmith Control Plane
        langsmith_api_key=cfg.require_secret("langsmithApiKey"),
        langsmith_workspace_id=cfg.require("langsmithWorkspaceId"),
        # AWS
        aws_profile=cfg.get("awsProfile") or _AWS_PROFILE,
    )
