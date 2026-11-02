"""Unit tests for config loading."""

from ess_load_test.infra.config import _DEFAULT_WORKER_COUNT, LoadTestInfraConfig


class TestLoadTestInfraConfig:
    def test_defaults(self):
        config = LoadTestInfraConfig(
            environment="dev",
            instance_type="t3.large",
            master_instance_type="t3.small",
            worker_count=_DEFAULT_WORKER_COUNT,
            use_default_vpc=True,
            vpc_id_override=None,
            subnet_ids_override=(),
        )
        assert config.worker_count == _DEFAULT_WORKER_COUNT
        assert config.use_default_vpc is True
