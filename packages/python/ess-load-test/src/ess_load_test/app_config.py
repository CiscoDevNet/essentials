"""Application configuration for load-test shells and the generic CLI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocustSyncFile:
    """Local file synced to a remote path on EC2 via SSM."""

    local_path: Path
    remote_path: str


@dataclass(frozen=True)
class LocustBundle:
    """Set of Locust sources synced to cluster instances before a run."""

    sync_files: tuple[LocustSyncFile, ...]


@dataclass(frozen=True)
class OAuthSettings:
    """OAuth client-credentials environment variable names and fallbacks.

    ``default_token_url`` is used when no token-URL environment variable is
    set. Leave it empty to require one.
    """

    default_token_url: str = ""
    client_id_env: str = "LOAD_TEST_OAUTH_CLIENT_ID"
    client_secret_env: str = "LOAD_TEST_OAUTH_CLIENT_SECRET"
    token_url_env: str = "LOAD_TEST_OAUTH_TOKEN_URL"
    client_id_fallback_envs: tuple[str, ...] = ()
    client_secret_fallback_envs: tuple[str, ...] = ()
    token_url_fallback_envs: tuple[str, ...] = ()


@dataclass(frozen=True)
class AppConfig:
    """Wiring for a load-test CLI shell or the generic ess-load-test tool."""

    pulumi_project_dir: Path
    locust_install_dir: str
    locust_bundle: LocustBundle
    valid_scenarios: frozenset[str]
    scenario_choices: tuple[str, ...]
    default_scenario: str
    ui_default_scenario: str
    default_profile: str
    default_stack: str
    default_region: str
    oauth: OAuthSettings
    browser_profile_dir: Path
    component_name: str
    pulumi_config_namespace: str | None = None
    # IdP hosts beyond ess-browser's public AUTH_DOMAINS. Browser auth
    # mistakes an unrecognized login page for the target and never waits.
    extra_auth_domains: tuple[str, ...] = ()
    # The Project tag on every cluster resource; component_name when unset.
    # Changing it on a live stack retags every resource on the next deploy.
    project_tag: str | None = None

    @property
    def config_namespace(self) -> str:
        return self.pulumi_config_namespace or self.component_name


def default_app_config() -> AppConfig:
    """Build generic ess-load-test defaults for the standalone CLI."""
    package_root = Path(__file__).resolve().parents[2]
    install_dir = "/opt/ess-load-test"
    locust_dir = Path(__file__).resolve().parent / "locust"
    return AppConfig(
        pulumi_project_dir=package_root,
        locust_install_dir=install_dir,
        locust_bundle=LocustBundle(
            sync_files=(
                LocustSyncFile(
                    local_path=locust_dir / "locustfile.py",
                    remote_path=f"{install_dir}/locustfile.py",
                ),
                LocustSyncFile(
                    local_path=locust_dir / "runtime.py",
                    remote_path=f"{install_dir}/locust_runtime.py",
                ),
                LocustSyncFile(
                    local_path=locust_dir / "scenario_default.py",
                    remote_path=f"{install_dir}/scenario_default.py",
                ),
            ),
        ),
        valid_scenarios=frozenset({"default"}),
        scenario_choices=("default",),
        default_scenario="default",
        ui_default_scenario="default",
        default_profile="dev",
        default_stack="dev",
        default_region="us-east-1",
        oauth=OAuthSettings(),
        browser_profile_dir=Path.home() / ".ess-load-test" / "browser-profile",
        component_name="ess-load-test",
    )
