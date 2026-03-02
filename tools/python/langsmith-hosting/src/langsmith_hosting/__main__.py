"""LangSmith Hybrid infrastructure on AWS provisioned with Pulumi.

Creates the full LangSmith Hybrid stack:
  1. VPC with public/private subnets across 3 AZs
  2. EKS cluster with managed node group, EBS CSI driver, and Helm addons
  3. RDS PostgreSQL instance
  4. ElastiCache Redis cluster
  5. S3 bucket with VPC endpoint
  6. LangSmith data plane (listener, KEDA, langgraph-dataplane Helm chart)

Resource dependency chain:
  VPC -> EKS -> EBS CSI -> Helm addons -> GP3 storage class
  VPC -> Postgres (+ random password)
  VPC -> Redis
  VPC -> S3
  EKS -> Listener (API) -> langgraph-dataplane (Helm)
  EKS -> KEDA (Helm) -> langgraph-dataplane (Helm)
"""

import pulumi
import pulumi_aws as aws
from dotenv import load_dotenv

from langsmith_hosting.config import load_config
from langsmith_hosting.dataplane import create_dataplane
from langsmith_hosting.eks import create_eks_cluster
from langsmith_hosting.postgres import create_postgres
from langsmith_hosting.redis import create_redis
from langsmith_hosting.s3 import create_s3
from langsmith_hosting.vpc import create_vpc

load_dotenv()

# =============================================================================
# Configuration
# =============================================================================
cfg = load_config()

# Get current AWS account and region
current = aws.get_caller_identity()
region = aws.get_region()

# =============================================================================
# VPC (Step 1 in apply-targeted.sh)
# =============================================================================
vpc = create_vpc(
    cluster_name=cfg.eks_cluster_name,
    cidr_block=cfg.vpc_cidr,
)

# =============================================================================
# EKS (Steps 2-7 in apply-targeted.sh)
# =============================================================================
eks = create_eks_cluster(
    cluster_name=cfg.eks_cluster_name,
    cluster_version=cfg.eks_cluster_version,
    vpc_id=vpc.vpc_id,
    private_subnet_ids=vpc.private_subnet_ids,
    public_subnet_ids=vpc.public_subnet_ids,
    node_instance_type=cfg.eks_node_instance_type,
    node_min_size=cfg.eks_node_min_size,
    node_max_size=cfg.eks_node_max_size,
    node_desired_size=cfg.eks_node_desired_size,
)

# =============================================================================
# PostgreSQL (Step 8 in apply-targeted.sh)
# =============================================================================
postgres = create_postgres(
    name=f"{cfg.eks_cluster_name}-postgres",
    vpc_id=vpc.vpc_id,
    subnet_ids=vpc.private_subnet_ids,
    vpc_cidr_block=vpc.vpc_cidr_block,
    instance_class=cfg.postgres_instance_class,
    engine_version=cfg.postgres_engine_version,
    allocated_storage=cfg.postgres_allocated_storage,
    max_allocated_storage=cfg.postgres_max_allocated_storage,
)

# =============================================================================
# Redis (Step 9 in apply-targeted.sh)
# =============================================================================
redis = create_redis(
    name=f"{cfg.eks_cluster_name}-redis",
    vpc_id=vpc.vpc_id,
    subnet_ids=vpc.private_subnet_ids,
    vpc_cidr_block=vpc.vpc_cidr_block,
    node_type=cfg.redis_node_type,
)

# =============================================================================
# S3 (Step 10 in apply-targeted.sh)
# =============================================================================
bucket_name = f"{cfg.s3_bucket_prefix}-{cfg.environment}-{current.account_id}"

s3 = create_s3(
    bucket_name=bucket_name,
    vpc_id=vpc.vpc_id,
    region=region.region,
)

# =============================================================================
# Data Plane (Listener + KEDA + langgraph-dataplane)
# =============================================================================
dataplane = create_dataplane(
    cluster_name=cfg.eks_cluster_name,
    k8s_provider=eks.k8s_provider,
    langsmith_api_key=cfg.langsmith_api_key,
    langsmith_workspace_id=cfg.langsmith_workspace_id,
)

# =============================================================================
# Exports
# =============================================================================
pulumi.export("aws_account_id", current.account_id)
pulumi.export("aws_region", region.region)

# VPC
pulumi.export("vpc_id", vpc.vpc_id)
pulumi.export("private_subnet_ids", vpc.private_subnet_ids)
pulumi.export("nat_gateway_public_ips", vpc.nat_gateway_public_ips)

# EKS
pulumi.export("eks_cluster_name", eks.cluster_name)
pulumi.export("eks_oidc_provider_arn", eks.oidc_provider_arn)

# PostgreSQL
pulumi.export("postgres_connection_url", postgres.connection_url)

# S3
pulumi.export("s3_bucket_name", s3.bucket_name)

# Data Plane
pulumi.export("langsmith_listener_id", dataplane.listener_id)

# kubectl configuration command
_kubectl_parts = [
    "aws eks update-kubeconfig --region ",
    region.region,
    " --name ",
    eks.cluster_name,
]
if cfg.aws_profile:
    _kubectl_parts.extend([" --profile ", cfg.aws_profile])

pulumi.export("kubectl_config_command", pulumi.Output.concat(*_kubectl_parts))
