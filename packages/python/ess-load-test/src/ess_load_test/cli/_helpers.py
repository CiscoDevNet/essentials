"""Shared Click helpers for load-test CLI commands."""

# pylint: disable=too-many-arguments,too-many-positional-arguments

from pathlib import Path

import click

from ess_load_test.app_config import AppConfig
from ess_load_test.auth import (
    BrowserAuthError,
    OAuthCredentialsError,
    establish_browser_session,
    fetch_auth_header_via_browser,
    fetch_bearer_token,
    format_auth_header,
)
from ess_load_test.cli.load_params import LoadTestParams
from ess_load_test.cluster import StackOutputError
from ess_load_test.ui import UiWorkflowConfig, UiWorkflowError, resolve_auth_header

ENV_TARGET_URL = "LOAD_TEST_TARGET_URL"
ENV_AWS_PROFILE = "LOAD_TEST_AWS_PROFILE"
ENV_STACK = "LOAD_TEST_STACK"
ENV_AWS_REGION = "LOAD_TEST_AWS_REGION"
ENV_SCENARIO = "LOAD_TEST_SCENARIO"


def _browser_profile_dir(app_config: AppConfig, override: str | None) -> Path:
    if override:
        return Path(override)
    return app_config.browser_profile_dir


def resolve_cli_auth_header(  # noqa: PLR0913
    app_config: AppConfig,
    explicit_header: str | None,
    *,
    fetch_token: bool,
    browser_auth: bool = False,
    target_url: str = "",
    headed: bool = False,
    browser_profile_dir: str | None = None,
) -> str | None:
    profile_dir = _browser_profile_dir(app_config, browser_profile_dir)
    if browser_auth:

        def resolve_browser() -> str:
            return fetch_auth_header_via_browser(
                target_url,
                headed=headed,
                profile_dir=profile_dir,
                extra_auth_domains=app_config.extra_auth_domains,
            )

        return resolve_auth_header(
            explicit_header,
            fetch_token=fetch_token,
            resolve_token=resolve_browser,
        )

    return resolve_auth_header(
        explicit_header,
        fetch_token=fetch_token,
        resolve_token=lambda: format_auth_header(fetch_bearer_token(app_config.oauth)),
    )


def make_resolve_token(config: UiWorkflowConfig):
    profile_dir = _browser_profile_dir(
        config.app_config,
        config.browser_profile_dir,
    )
    if config.browser_auth:
        return lambda: fetch_auth_header_via_browser(
            config.target_url,
            headed=config.headed,
            profile_dir=profile_dir,
            extra_auth_domains=config.app_config.extra_auth_domains,
        )
    return lambda: format_auth_header(fetch_bearer_token(config.app_config.oauth))


def browser_auth_options(app_config: AppConfig):
    """Decorator factory for system-Chrome SSO auth options."""

    def decorator(func):
        func = click.option(
            "--browser-auth",
            is_flag=True,
            help=(
                "Authenticate via system Chrome SSO instead of OAuth client "
                "credentials."
            ),
        )(func)
        func = click.option(
            "--headed",
            is_flag=True,
            default=False,
            help="Show system Chrome (required on first browser SSO login).",
        )(func)
        func = click.option(
            "--browser-profile-dir",
            default=None,
            help=(
                f"Chrome profile directory [default: {app_config.browser_profile_dir}]"
            ),
        )(func)
        return func

    return decorator


def scenario_option(app_config: AppConfig, *, default: str, show_default: bool = True):
    """Decorator factory for Locust scenario selection."""

    def decorator(func):
        return click.option(
            "--scenario",
            default=default,
            envvar=ENV_SCENARIO,
            show_default=show_default,
            type=click.Choice(app_config.scenario_choices),
            help="Locust user scenario.",
        )(func)

    return decorator


def workflow_options(app_config: AppConfig):
    """Decorator factory for shared UI workflow options."""

    def decorator(func):
        func = click.option(
            "--path",
            "paths",
            default="/",
            show_default=True,
            help="Comma-separated HTTP paths to request.",
        )(func)
        func = click.option(
            "--auth-header",
            default=None,
            envvar="LOAD_TEST_AUTH_HEADER",
            help="Optional auth header value or 'Header-Name: value'.",
        )(func)
        func = click.option(
            "--fetch-token/--no-fetch-token",
            default=True,
            show_default=True,
            help=(
                "Fetch OAuth token when credentials are set and --auth-header "
                "is omitted."
            ),
        )(func)
        func = click.option(
            "--stack",
            default=app_config.default_stack,
            envvar=ENV_STACK,
            show_default=True,
            help="Pulumi stack name.",
        )(func)
        func = click.option(
            "--profile",
            default=app_config.default_profile,
            envvar=ENV_AWS_PROFILE,
            show_default=True,
            help="AWS profile name.",
        )(func)
        func = click.option(
            "--region",
            default=None,
            envvar=ENV_AWS_REGION,
            help="AWS region (defaults to stack output).",
        )(func)
        func = click.option(
            "--local-port",
            default=8089,
            show_default=True,
            help="Local port for Locust UI port-forward.",
        )(func)
        return func

    return decorator


def workflow_config(  # noqa: PLR0913
    app_config: AppConfig,
    *,
    url: str | None,
    paths: str,
    scenario: str | None = None,
    auth_header: str | None,
    fetch_token: bool,
    stack: str,
    profile: str,
    region: str | None,
    local_port: int,
    browser_auth: bool = False,
    headed: bool = False,
    browser_profile_dir: str | None = None,
    load_params: LoadTestParams | None = None,
) -> UiWorkflowConfig:
    return UiWorkflowConfig(
        app_config=app_config,
        target_url=url or "",
        paths=paths,
        scenario=scenario,
        stack=stack,
        profile=profile,
        region=region,
        local_port=local_port,
        fetch_token=fetch_token,
        auth_header=auth_header,
        browser_auth=browser_auth,
        headed=headed,
        browser_profile_dir=browser_profile_dir,
        load_params=load_params,
    )


def handle_workflow_error(exc: Exception) -> None:
    if isinstance(
        exc,
        (StackOutputError, UiWorkflowError, OAuthCredentialsError, BrowserAuthError),
    ):
        raise click.ClickException(str(exc)) from exc
    raise exc


def browser_login_command_factory(app_config: AppConfig):
    @click.command("login")
    @click.option(
        "--url",
        required=True,
        envvar=ENV_TARGET_URL,
        help="Target base URL (scheme + host).",
    )
    @click.option(
        "--headed/--headless",
        default=True,
        show_default=True,
        help="Show system Chrome (use --headless only with a saved profile).",
    )
    @click.option(
        "--browser-profile-dir",
        default=None,
        help=(f"Chrome profile directory [default: {app_config.browser_profile_dir}]"),
    )
    def browser_login_command(
        url: str,
        headed: bool,
        browser_profile_dir: str | None,
    ) -> None:
        """Open system Chrome, complete SSO, and save the session profile."""
        try:
            establish_browser_session(
                url,
                headed=headed,
                profile_dir=_browser_profile_dir(app_config, browser_profile_dir),
                extra_auth_domains=app_config.extra_auth_domains,
            )
        except BrowserAuthError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo("OK: browser session established")

    return browser_login_command
