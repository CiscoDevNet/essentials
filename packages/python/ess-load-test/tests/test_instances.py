"""Unit tests for EC2 instance provisioning helpers."""

from ess_load_test.app_config import default_app_config
from ess_load_test.infra.constants import get_tags
from ess_load_test.infra.instances import (
    EC2_USER_DATA_MAX_BYTES,
    _build_user_data,
    controller_hostname,
    worker_hostname,
)


def test_controller_hostname() -> None:
    assert controller_hostname("load-test-team-dev") == (
        "load-test-team-dev-locust-controller"
    )


def test_worker_hostname() -> None:
    assert worker_hostname("load-test-team-dev", 0) == (
        "load-test-team-dev-locust-worker-0"
    )


def test_build_user_data_sets_hostname() -> None:
    app_config = default_app_config()
    hostname = "load-test-dev-locust-controller"
    user_data = _build_user_data(
        hostname,
        locust_install_dir=app_config.locust_install_dir,
        cloud_init_files=app_config.locust_bundle.sync_files,
    )
    assert f"hostname: {hostname}" in user_data
    assert f"hostnamectl set-hostname {hostname}" in user_data
    assert "write_files:" not in user_data
    assert len(user_data.encode()) <= EC2_USER_DATA_MAX_BYTES


def test_get_tags_includes_managed_by_and_environment() -> None:
    tags = get_tags(
        "ess-load-test",
        "team-dev",
        {"Name": "example", "Role": "locust-worker"},
    )
    assert tags["ManagedBy"] == "pulumi"
    assert tags["Environment"] == "team-dev"
    assert tags["Name"] == "example"
    assert tags["Role"] == "locust-worker"


def test_get_tags_project_defaults_to_component() -> None:
    assert get_tags("ess-load-test", "dev")["Project"] == "ess-load-test"


def test_get_tags_project_tag_overrides_component() -> None:
    tags = get_tags("ess-load-test", "dev", project_tag="my-monorepo")
    assert tags["Project"] == "my-monorepo"
    assert tags["Component"] == "ess-load-test"
