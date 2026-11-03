"""Network discovery and security group resources."""

from dataclasses import dataclass

import pulumi
import pulumi_aws as aws

from ess_load_test.infra.config import LoadTestInfraConfig
from ess_load_test.infra.constants import get_tags

_LOCUST_MASTER_PORT = 5557
_LOCUST_STATS_PORT = 5558


@dataclass(frozen=True)
class NetworkPlacement:
    """Resolved VPC and subnet for EC2 instances."""

    vpc_id: str
    subnet_id: str


@dataclass
class NetworkOutputs:
    """Outputs from the network module."""

    placement: NetworkPlacement
    security_group_id: pulumi.Output[str]


def resolve_network_placement(
    config: LoadTestInfraConfig,
    *,
    config_namespace: str,
) -> NetworkPlacement:
    """Resolve VPC and subnet IDs for instance placement."""
    has_vpc_override = bool(config.vpc_id_override)
    has_subnet_override = bool(config.subnet_ids_override)
    if has_vpc_override != has_subnet_override:
        msg = (
            f"{config_namespace}:vpcId and {config_namespace}:subnetIds must both "
            "be set when overriding network placement."
        )
        raise ValueError(msg)

    if has_vpc_override and has_subnet_override:
        return NetworkPlacement(
            vpc_id=config.vpc_id_override,
            subnet_id=config.subnet_ids_override[0],
        )

    if not config.use_default_vpc:
        msg = (
            "useDefaultVpc is false but vpcId/subnetIds overrides are not set. "
            f"Set {config_namespace}:vpcId and {config_namespace}:subnetIds."
        )
        raise ValueError(msg)

    default_vpc = aws.ec2.get_vpc(default=True)
    subnets = aws.ec2.get_subnets(
        filters=[
            aws.ec2.GetSubnetsFilterArgs(name="vpc-id", values=[default_vpc.id]),
            aws.ec2.GetSubnetsFilterArgs(name="default-for-az", values=["true"]),
        ],
    )
    if not subnets.ids:
        msg = "No default-for-az subnets found in the default VPC."
        raise ValueError(msg)

    return NetworkPlacement(vpc_id=default_vpc.id, subnet_id=subnets.ids[0])


def build_locust_security_group_egress() -> list[aws.ec2.SecurityGroupEgressArgs]:
    """Return egress rules for Locust load generator instances."""
    return [
        aws.ec2.SecurityGroupEgressArgs(
            protocol="tcp",
            from_port=80,
            to_port=80,
            cidr_blocks=["0.0.0.0/0"],
            description="HTTP outbound for apt/bootstrap on instance launch",
        ),
        aws.ec2.SecurityGroupEgressArgs(
            protocol="tcp",
            from_port=443,
            to_port=443,
            cidr_blocks=["0.0.0.0/0"],
            description="HTTPS outbound to apt mirrors, PyPI, and load test targets",
        ),
        aws.ec2.SecurityGroupEgressArgs(
            protocol="udp",
            from_port=53,
            to_port=53,
            cidr_blocks=["0.0.0.0/0"],
            description="DNS (UDP) outbound",
        ),
        aws.ec2.SecurityGroupEgressArgs(
            protocol="tcp",
            from_port=53,
            to_port=53,
            cidr_blocks=["0.0.0.0/0"],
            description="DNS (TCP) outbound",
        ),
        aws.ec2.SecurityGroupEgressArgs(
            protocol="tcp",
            from_port=_LOCUST_MASTER_PORT,
            to_port=_LOCUST_STATS_PORT,
            self=True,
            description="Locust worker to master coordination and stats",
        ),
    ]


def build_locust_security_group_ingress() -> list[aws.ec2.SecurityGroupIngressArgs]:
    """Return ingress rules for Locust master/worker coordination."""
    return [
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=_LOCUST_MASTER_PORT,
            to_port=_LOCUST_STATS_PORT,
            self=True,
            description="Locust worker to master coordination and stats",
        ),
    ]


def has_public_internet_ingress(
    ingress_rules: list[aws.ec2.SecurityGroupIngressArgs],
) -> bool:
    """Return True if any ingress rule allows traffic from the public internet."""
    for rule in ingress_rules:
        cidr_blocks = rule.cidr_blocks or []
        if "0.0.0.0/0" in cidr_blocks:
            return True
        ipv6_cidr_blocks = rule.ipv6_cidr_blocks or []
        if "::/0" in ipv6_cidr_blocks:
            return True
    return False


def create_network(
    resource_prefix: str,
    placement: NetworkPlacement,
    *,
    component_name: str,
    environment: str,
    project_tag: str | None = None,
) -> NetworkOutputs:
    """Create the Locust cluster security group."""
    ingress_rules = build_locust_security_group_ingress()
    security_group = aws.ec2.SecurityGroup(
        f"{resource_prefix}-locust-sg",
        name=f"{resource_prefix}-locust-sg",
        description="Security group for Locust load test EC2 instances",
        vpc_id=placement.vpc_id,
        ingress=ingress_rules,
        egress=build_locust_security_group_egress(),
        tags=get_tags(
            component_name,
            environment,
            {"Name": f"{resource_prefix}-locust-sg"},
            project_tag=project_tag,
        ),
        opts=pulumi.ResourceOptions(delete_before_replace=False),
    )

    return NetworkOutputs(
        placement=placement,
        security_group_id=security_group.id,
    )
