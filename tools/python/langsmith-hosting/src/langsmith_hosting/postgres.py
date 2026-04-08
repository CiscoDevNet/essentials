"""RDS PostgreSQL resources for LangSmith Hosting infrastructure.

Creates an RDS PostgreSQL instance with a dedicated subnet group and
security group, matching the Terraform module.postgres configuration.
"""

from dataclasses import dataclass

import pulumi
import pulumi_aws as aws
import pulumi_random as random

from langsmith_hosting.constants import get_tags


@dataclass
class PostgresOutputs:
    """Outputs from the Postgres module."""

    instance_endpoint: pulumi.Output[str]
    instance_address: pulumi.Output[str]
    instance_port: pulumi.Output[int]
    connection_url: pulumi.Output[str]
    password: pulumi.Output[str]


def create_postgres(  # noqa: PLR0913
    name: str,
    vpc_id: pulumi.Output[str],
    subnet_ids: pulumi.Output[list[str]],
    vpc_cidr_block: pulumi.Output[str],
    instance_class: str,
    engine_version: str,
    allocated_storage: int,
    max_allocated_storage: int,
    username: str = "langsmith",
) -> PostgresOutputs:
    """Create an RDS PostgreSQL instance for LangSmith.

    Args:
        name: Resource name prefix (e.g. "langsmith-hybrid-dev-postgres").
        vpc_id: VPC ID for the security group.
        subnet_ids: Private subnet IDs for the DB subnet group.
        vpc_cidr_block: VPC CIDR block for ingress rules.
        instance_class: RDS instance class (e.g. "db.t3.medium").
        engine_version: PostgreSQL engine version (e.g. "16.6").
        allocated_storage: Initial storage in GB.
        max_allocated_storage: Maximum storage for autoscaling in GB.
        username: Database master username.

    Returns:
        PostgresOutputs with connection details.
    """
    tags = get_tags("postgres")
    # =========================================================================
    # Random password for PostgreSQL
    # =========================================================================
    password = random.RandomPassword(
        f"{name}-password",
        length=32,
        special=False,
    )

    # =========================================================================
    # DB subnet group
    # =========================================================================
    subnet_group = aws.rds.SubnetGroup(
        f"{name}-subnet-group",
        name=name,
        subnet_ids=subnet_ids,
        tags={**tags, "Name": f"{name}-subnet-group"},
    )

    # =========================================================================
    # Security group allowing PostgreSQL access from within the VPC
    # =========================================================================
    sg = aws.ec2.SecurityGroup(
        f"{name}-sg",
        name=f"{name}-sg",
        description=f"Security group for {name} RDS instance",
        vpc_id=vpc_id,
        ingress=[
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=5432,
                to_port=5432,
                cidr_blocks=[vpc_cidr_block],
                description="PostgreSQL access from VPC",
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
    # RDS instance
    # =========================================================================
    db = aws.rds.Instance(
        name,
        identifier=name,
        engine="postgres",
        engine_version=engine_version,
        instance_class=instance_class,
        allocated_storage=allocated_storage,
        max_allocated_storage=max_allocated_storage,
        db_name="langsmith",
        username=username,
        password=password.result,
        db_subnet_group_name=subnet_group.name,
        vpc_security_group_ids=[sg.id],
        skip_final_snapshot=True,
        publicly_accessible=False,
        storage_encrypted=True,
        tags={**tags, "Name": name},
    )

    # Build connection URL
    connection_url = pulumi.Output.all(
        db.username,
        password.result,
        db.address,
        db.port,
        db.db_name,
    ).apply(
        lambda args: f"postgresql://{args[0]}:{args[1]}@{args[2]}:{args[3]}/{args[4]}"
    )

    return PostgresOutputs(
        instance_endpoint=db.endpoint,
        instance_address=db.address,
        instance_port=db.port,
        connection_url=connection_url,
        password=password.result,
    )
