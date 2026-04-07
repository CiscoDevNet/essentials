"""ElastiCache Redis resources for LangSmith Hosting infrastructure.

Creates an ElastiCache Redis cluster with a dedicated subnet group and
security group, matching the Terraform module.redis configuration.
"""

from dataclasses import dataclass

import pulumi
import pulumi_aws as aws

from langsmith_hosting.constants import get_tags


@dataclass
class RedisOutputs:
    """Outputs from the Redis module."""

    cluster_id: pulumi.Output[str]
    cache_nodes: pulumi.Output[list]
    endpoint: pulumi.Output[str]
    port: pulumi.Output[int]


def create_redis(
    name: str,
    vpc_id: pulumi.Output[str],
    subnet_ids: pulumi.Output[list[str]],
    vpc_cidr_block: pulumi.Output[str],
    node_type: str,
) -> RedisOutputs:
    """Create an ElastiCache Redis cluster for LangSmith.

    Args:
        name: Resource name prefix (e.g. "langsmith-hybrid-dev-redis").
        vpc_id: VPC ID for the security group.
        subnet_ids: Private subnet IDs for the cache subnet group.
        vpc_cidr_block: VPC CIDR block for ingress rules.
        node_type: ElastiCache node type (e.g. "cache.t3.micro").

    Returns:
        RedisOutputs with cluster connection details.
    """
    tags = get_tags("redis")
    # =========================================================================
    # Cache subnet group
    # =========================================================================
    subnet_group = aws.elasticache.SubnetGroup(
        f"{name}-subnet-group",
        name=name,
        subnet_ids=subnet_ids,
        tags={**tags, "Name": f"{name}-subnet-group"},
    )

    # =========================================================================
    # Security group allowing Redis access from within the VPC
    # =========================================================================
    sg = aws.ec2.SecurityGroup(
        f"{name}-sg",
        name=f"{name}-sg",
        description=f"Security group for {name} ElastiCache cluster",
        vpc_id=vpc_id,
        ingress=[
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=6379,
                to_port=6379,
                cidr_blocks=[vpc_cidr_block],
                description="Redis access from VPC",
            )
        ],
        egress=[
            aws.ec2.SecurityGroupEgressArgs(
                protocol="-1",
                from_port=0,
                to_port=0,
                cidr_blocks=["0.0.0.0/0"],
                description="Allow all outbound",
            )
        ],
        tags={**tags, "Name": f"{name}-sg"},
    )

    # =========================================================================
    # ElastiCache Redis cluster
    # =========================================================================
    cluster = aws.elasticache.Cluster(
        name,
        cluster_id=name,
        engine="redis",
        engine_version="7.0",
        node_type=node_type,
        num_cache_nodes=1,
        subnet_group_name=subnet_group.name,
        security_group_ids=[sg.id],
        tags={**tags, "Name": name},
    )

    return RedisOutputs(
        cluster_id=cluster.cluster_id,
        cache_nodes=cluster.cache_nodes,
        endpoint=cluster.cache_nodes.apply(
            lambda nodes: nodes[0]["address"] if nodes else ""
        ),
        port=cluster.port,
    )
