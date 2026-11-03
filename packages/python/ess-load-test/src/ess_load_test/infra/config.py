"""Pulumi config loading for the Locust load test stack."""

from dataclasses import dataclass

import pulumi

_DEFAULT_ENVIRONMENT = "dev"
_DEFAULT_INSTANCE_TYPE = "t3.large"
_DEFAULT_MASTER_INSTANCE_TYPE = "t3.small"
_DEFAULT_WORKER_COUNT = 2


@dataclass(frozen=True)
class LoadTestInfraConfig:
    """Typed configuration for the load test infrastructure stack."""

    environment: str
    instance_type: str
    master_instance_type: str
    worker_count: int
    use_default_vpc: bool
    vpc_id_override: str | None
    subnet_ids_override: tuple[str, ...]


def load_config(config_namespace: str) -> LoadTestInfraConfig:
    """Load stack configuration from Pulumi config."""
    cfg = pulumi.Config(config_namespace)

    raw_subnet_ids = cfg.get("subnetIds")
    subnet_ids_override = tuple(
        subnet_id.strip()
        for subnet_id in (raw_subnet_ids or "").split(",")
        if subnet_id.strip()
    )

    worker_count = cfg.get_int("workerCount")
    if worker_count is None:
        worker_count = _DEFAULT_WORKER_COUNT

    return LoadTestInfraConfig(
        environment=cfg.get("environment") or _DEFAULT_ENVIRONMENT,
        instance_type=cfg.get("instanceType") or _DEFAULT_INSTANCE_TYPE,
        master_instance_type=cfg.get("masterInstanceType")
        or _DEFAULT_MASTER_INSTANCE_TYPE,
        worker_count=worker_count,
        use_default_vpc=cfg.get_bool("useDefaultVpc")
        if cfg.get("useDefaultVpc") is not None
        else True,
        vpc_id_override=cfg.get("vpcId"),
        subnet_ids_override=subnet_ids_override,
    )
