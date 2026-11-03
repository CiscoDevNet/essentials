"""Click CLI factory for load-test tools."""

# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals

import click
from botocore.exceptions import NoCredentialsError, NoRegionError, ProfileNotFound

from ess_load_test.app_config import AppConfig
from ess_load_test.auth import (
    BrowserAuthError,
    OAuthCredentialsError,
    fetch_auth_header_via_browser,
    fetch_bearer_token,
    format_auth_header,
    write_auth_header_env_file,
)
from ess_load_test.cli import _helpers as helpers
from ess_load_test.cli.load_params import (
    load_test_params_from_click,
    load_test_params_options,
)
from ess_load_test.cluster import (
    LoadTestRunRequest,
    StackOutputError,
    load_stack_outputs,
    reset_cluster_locust,
    run_load_test,
)
from ess_load_test.ui import (
    LocalPortExpectation,
    UiWorkflowError,
    check_local_port,
    cleanup_stale_port_forward,
    open_locust_ui,
    print_cluster_status,
    run_port_forward,
    run_preflight,
)


# One closure per command, all sharing app_config, so the size and branch
# count grow with the command list rather than with any one command.
def build_cli(app_config: AppConfig) -> click.Command:  # noqa: C901, PLR0915
    """Build a Click command group for load-test operations."""

    @click.group()
    def cli() -> None:
        """EC2 Locust load testing for HTTP targets."""

    @click.group()
    def browser() -> None:
        """System Chrome SSO login for load-test targets."""

    browser.add_command(helpers.browser_login_command_factory(app_config))

    @click.group()
    def ui() -> None:
        """Locust web UI: token, cluster start, and SSM port-forward."""

    @ui.command("open")
    @helpers.workflow_options(app_config)
    @helpers.browser_auth_options(app_config)
    @helpers.scenario_option(app_config, default=app_config.ui_default_scenario)
    @load_test_params_options(duration_default="10m", headless_exports=False)
    @click.option(
        "--url",
        required=True,
        envvar=helpers.ENV_TARGET_URL,
        help="Target base URL (scheme + host).",
    )
    def ui_open_command(  # noqa: PLR0913
        url: str,
        paths: str,
        scenario: str,
        users: int,
        spawn_rate: float,
        duration: str | None,
        user_class: tuple[str, ...],
        autostart: bool,
        autoquit: int | None,
        auth_header: str | None,
        fetch_token: bool,
        stack: str,
        profile: str,
        region: str | None,
        local_port: int,
        browser_auth: bool,
        headed: bool,
        browser_profile_dir: str | None,
    ) -> None:
        """Preflight, fetch auth, start Locust UI, and print port-forward."""
        load_params = load_test_params_from_click(
            users=users,
            spawn_rate=spawn_rate,
            duration=duration,
            user_class=user_class,
            autostart=autostart,
            autoquit=autoquit,
        )
        config = helpers.workflow_config(
            app_config,
            url=url,
            paths=paths,
            scenario=scenario,
            auth_header=auth_header,
            fetch_token=fetch_token,
            stack=stack,
            profile=profile,
            region=region,
            local_port=local_port,
            browser_auth=browser_auth,
            headed=headed,
            browser_profile_dir=browser_profile_dir,
            load_params=load_params,
        )
        try:
            _, forward_command = open_locust_ui(
                config,
                resolve_token=helpers.make_resolve_token(config),
            )
            print_cluster_status(config)
        except (
            RuntimeError,
            TimeoutError,
            OAuthCredentialsError,
            BrowserAuthError,
            UiWorkflowError,
        ) as exc:
            helpers.handle_workflow_error(exc)

        click.echo("")
        click.echo("Locust web UI started on the master (port 8089).")
        click.echo(f"Open http://localhost:{local_port} after port-forward.")
        click.echo("Port-forward command:")
        click.echo(forward_command)

    @ui.command("forward")
    @helpers.workflow_options(app_config)
    @click.option(
        "--exec",
        "exec_forward",
        is_flag=True,
        help="Run port-forward (blocking).",
    )
    def ui_forward_command(  # noqa: PLR0913
        paths: str,
        auth_header: str | None,
        fetch_token: bool,
        stack: str,
        profile: str,
        region: str | None,
        local_port: int,
        exec_forward: bool,
    ) -> None:
        """Print or run the SSM port-forward command for the Locust web UI."""
        config = helpers.workflow_config(
            app_config,
            url="",
            paths=paths,
            auth_header=auth_header,
            fetch_token=fetch_token,
            stack=stack,
            profile=profile,
            region=region,
            local_port=local_port,
        )
        try:
            forward_command = run_port_forward(config, exec_forward=exec_forward)
        except StackOutputError as exc:
            helpers.handle_workflow_error(exc)

        if not exec_forward:
            click.echo("Start the Locust master UI first (ui open), then:")
            click.echo(forward_command)

    @ui.command("cleanup-forward")
    @click.option(
        "--local-port",
        default=8089,
        show_default=True,
        help="Local Locust UI port to clear.",
    )
    def ui_cleanup_forward_command(local_port: int) -> None:
        """Kill stale local SSM port-forward processes and verify the port is free."""
        try:
            killed = cleanup_stale_port_forward(local_port)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc

        if killed:
            click.echo(
                f"Stopped stale port-forward process(es) ({killed} pkill match(es))."
            )
        else:
            click.echo("No stale port-forward processes found.")
        click.echo(f"OK: local port {local_port} is free")

    @ui.command("check-port")
    @click.option(
        "--local-port",
        default=8089,
        show_default=True,
        help="Local Locust UI port to inspect.",
    )
    @click.option(
        "--expect",
        type=click.Choice(["free", "listening"], case_sensitive=False),
        default="free",
        show_default=True,
        help="Exit 0 when the port matches this state (lsof exit 1 => free).",
    )
    def ui_check_port_command(local_port: int, expect: str) -> None:
        """Check local port state; exit 0 when --expect is met."""
        expectation = LocalPortExpectation(expect.lower())
        try:
            check_local_port(local_port, expect=expectation)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc

        if expectation == LocalPortExpectation.FREE:
            click.echo(f"OK: port {local_port} is free")
        else:
            click.echo(f"OK: port {local_port} is listening")

    @ui.command("reset-cluster")
    @click.option(
        "--stack",
        default=app_config.default_stack,
        envvar=helpers.ENV_STACK,
        show_default=True,
        help="Pulumi stack name.",
    )
    @click.option(
        "--profile",
        default=app_config.default_profile,
        envvar=helpers.ENV_AWS_PROFILE,
        show_default=True,
        help="AWS profile name.",
    )
    @click.option(
        "--region",
        default=app_config.default_region,
        envvar=helpers.ENV_AWS_REGION,
        show_default=True,
        help="AWS region.",
    )
    def ui_reset_cluster_command(stack: str, profile: str, region: str) -> None:
        """Stop stale Locust processes on all EC2 instances.

        Frees the master ports 5557–5558 and the web UI port 8089.
        """
        try:
            reset_cluster_locust(
                stack=stack,
                profile=profile,
                region=region,
                app_config=app_config,
            )
        except (StackOutputError, RuntimeError, TimeoutError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo("OK: Locust processes stopped on all cluster instances")

    @ui.command("preflight")
    @helpers.workflow_options(app_config)
    @click.option(
        "--url",
        required=True,
        envvar=helpers.ENV_TARGET_URL,
        help="Target base URL (scheme + host).",
    )
    def ui_preflight_command(  # noqa: PLR0913
        url: str,
        paths: str,
        auth_header: str | None,
        fetch_token: bool,
        stack: str,
        profile: str,
        region: str | None,
        local_port: int,
    ) -> None:
        """Check AWS credentials and target URL before starting Locust."""
        config = helpers.workflow_config(
            app_config,
            url=url,
            paths=paths,
            auth_header=auth_header,
            fetch_token=fetch_token,
            stack=stack,
            profile=profile,
            region=region,
            local_port=local_port,
        )
        try:
            run_preflight(config)
        except UiWorkflowError as exc:
            helpers.handle_workflow_error(exc)
        click.echo("OK: preflight passed")

    cli.add_command(browser)
    cli.add_command(ui)

    @click.command("fetch-token")
    @click.option(
        "--url",
        default=None,
        envvar=helpers.ENV_TARGET_URL,
        help="Target base URL (required for --browser-auth).",
    )
    @click.option(
        "--browser-auth",
        is_flag=True,
        help="Log in via system Chrome SSO instead of OAuth client credentials.",
    )
    @click.option(
        "--headed",
        is_flag=True,
        default=False,
        help="Show system Chrome (use on first browser SSO login).",
    )
    @click.option(
        "--browser-profile-dir",
        default=None,
        help=(f"Chrome profile directory [default: {app_config.browser_profile_dir}]"),
    )
    @click.option(
        "--write-env-file",
        type=click.Path(dir_okay=False),
        default=None,
        help="Write export LOAD_TEST_AUTH_HEADER=... to this file (mode 600).",
    )
    @click.option(
        "--print-header/--no-print-header",
        default=False,
        help="Print the auth header to stdout (avoid in shared logs).",
    )
    def fetch_token_command(  # noqa: PLR0913
        url: str | None,
        browser_auth: bool,
        headed: bool,
        browser_profile_dir: str | None,
        write_env_file: str | None,
        print_header: bool,
    ) -> None:
        """Fetch auth for load tests (client credentials or system Chrome SSO)."""
        try:
            if browser_auth:
                if not url:
                    raise click.ClickException(
                        "--url or LOAD_TEST_TARGET_URL is required for --browser-auth"
                    )
                header = fetch_auth_header_via_browser(
                    url,
                    headed=headed,
                    profile_dir=helpers._browser_profile_dir(  # noqa: SLF001
                        app_config,
                        browser_profile_dir,
                    ),
                    extra_auth_domains=app_config.extra_auth_domains,
                )
            else:
                token = fetch_bearer_token(app_config.oauth)
                header = format_auth_header(token)
        except (OAuthCredentialsError, BrowserAuthError) as exc:
            raise click.ClickException(str(exc)) from exc

        if write_env_file:
            write_auth_header_env_file(write_env_file, header)
            click.echo(f"Wrote auth header env file: {write_env_file}")
        if print_header:
            click.echo(header)
        if not write_env_file and not print_header:
            click.echo(
                "Auth header fetched. Use --write-env-file or --print-header "
                "to export it."
            )

    @click.command("run")
    @helpers.browser_auth_options(app_config)
    @click.option(
        "--url",
        required=True,
        envvar=helpers.ENV_TARGET_URL,
        help="Target base URL (scheme + host).",
    )
    @click.option(
        "--path",
        "paths",
        default="/",
        show_default=True,
        help="Comma-separated HTTP paths to request.",
    )
    @load_test_params_options(duration_default="5m", headless_exports=True)
    @click.option(
        "--auth-header",
        default=None,
        envvar="LOAD_TEST_AUTH_HEADER",
        help="Optional auth header value or 'Header-Name: value'.",
    )
    @click.option(
        "--fetch-token/--no-fetch-token",
        default=True,
        show_default=True,
        help="Fetch OAuth token when credentials are set and --auth-header is omitted.",
    )
    @click.option(
        "--stack",
        default=app_config.default_stack,
        envvar=helpers.ENV_STACK,
        show_default=True,
        help="Pulumi stack name.",
    )
    @click.option(
        "--profile",
        default=None,
        envvar=helpers.ENV_AWS_PROFILE,
        help="AWS profile name.",
    )
    @click.option(
        "--region",
        default=None,
        envvar=helpers.ENV_AWS_REGION,
        help="AWS region (defaults to stack output).",
    )
    @helpers.scenario_option(app_config, default=app_config.default_scenario)
    def run_command(  # noqa: PLR0913
        scenario: str,
        browser_auth: bool,
        headed: bool,
        browser_profile_dir: str | None,
        url: str,
        paths: str,
        users: int,
        spawn_rate: float,
        duration: str | None,
        user_class: tuple[str, ...],
        autostart: bool,
        autoquit: int | None,
        csv_prefix: str | None,
        html_path: str | None,
        reset_stats: bool,
        auth_header: str | None,
        fetch_token: bool,
        stack: str,
        profile: str | None,
        region: str | None,
    ) -> None:
        """Run a headless Locust load test against a URL."""
        load_params = load_test_params_from_click(
            users=users,
            spawn_rate=spawn_rate,
            duration=duration,
            user_class=user_class,
            autostart=autostart,
            autoquit=autoquit,
            csv_prefix=csv_prefix,
            html_path=html_path,
            reset_stats=reset_stats,
        )
        try:
            outputs = load_stack_outputs(stack, app_config.pulumi_project_dir)
            resolved_region = region or str(outputs.get("region", ""))
            resolved_auth = auth_header
            if fetch_token and not resolved_auth:
                resolved_auth = helpers.resolve_cli_auth_header(
                    app_config,
                    None,
                    fetch_token=True,
                    browser_auth=browser_auth,
                    target_url=url,
                    headed=headed,
                    browser_profile_dir=browser_profile_dir,
                )
            request = LoadTestRunRequest(
                stack=stack,
                target_url=url,
                paths=paths,
                scenario=scenario,
                load_params=load_params,
                auth_header=resolved_auth,
                profile=profile,
                region=resolved_region or None,
            )
            stdout = run_load_test(request, app_config)
        except (
            StackOutputError,
            RuntimeError,
            TimeoutError,
            OAuthCredentialsError,
            BrowserAuthError,
            NoCredentialsError,
            NoRegionError,
            ProfileNotFound,
        ) as exc:
            raise click.ClickException(str(exc)) from exc

        click.echo(stdout)

    @click.command("status")
    @click.option(
        "--stack",
        default=app_config.default_stack,
        envvar=helpers.ENV_STACK,
        show_default=True,
        help="Pulumi stack name.",
    )
    @click.option(
        "--profile",
        default=app_config.default_profile,
        envvar=helpers.ENV_AWS_PROFILE,
        show_default=True,
        help="AWS profile name.",
    )
    @click.option(
        "--region",
        default=None,
        envvar=helpers.ENV_AWS_REGION,
        help="AWS region (defaults to stack output).",
    )
    def status_command(stack: str, profile: str, region: str | None) -> None:
        """Show Pulumi outputs and SSM reachability for the load test cluster."""
        config = helpers.workflow_config(
            app_config,
            url="https://app.example.com",
            paths="/",
            auth_header=None,
            fetch_token=False,
            stack=stack,
            profile=profile,
            region=region,
            local_port=8089,
        )
        try:
            print_cluster_status(config)
        except (StackOutputError, UiWorkflowError) as exc:
            raise click.ClickException(str(exc)) from exc

    @click.command("ui-start", hidden=True)
    @click.option(
        "--url",
        required=True,
        envvar=helpers.ENV_TARGET_URL,
        help="Target base URL (scheme + host).",
    )
    @click.option("--path", "paths", default="/", show_default=True)
    @click.option("--auth-header", default=None, envvar="LOAD_TEST_AUTH_HEADER")
    @click.option("--fetch-token/--no-fetch-token", default=True, show_default=True)
    @click.option(
        "--stack",
        default=app_config.default_stack,
        envvar=helpers.ENV_STACK,
        show_default=True,
    )
    @click.option(
        "--profile",
        default=app_config.default_profile,
        envvar=helpers.ENV_AWS_PROFILE,
        show_default=True,
    )
    @click.option(
        "--region",
        default=app_config.default_region,
        envvar=helpers.ENV_AWS_REGION,
        show_default=True,
    )
    def ui_start_legacy_command(  # noqa: PLR0913
        url: str,
        paths: str,
        auth_header: str | None,
        fetch_token: bool,
        stack: str,
        profile: str,
        region: str,
    ) -> None:
        """Deprecated: use `ui open`."""
        ctx = click.get_current_context()
        ctx.invoke(
            ui_open_command,
            url=url,
            paths=paths,
            scenario=app_config.ui_default_scenario,
            auth_header=auth_header,
            fetch_token=fetch_token,
            stack=stack,
            profile=profile,
            region=region,
            local_port=8089,
            browser_auth=False,
            headed=False,
            browser_profile_dir=None,
        )

    @click.command("ui-forward", hidden=True)
    @click.option(
        "--stack",
        default=app_config.default_stack,
        envvar=helpers.ENV_STACK,
        show_default=True,
    )
    @click.option(
        "--profile",
        default=app_config.default_profile,
        envvar=helpers.ENV_AWS_PROFILE,
        show_default=True,
    )
    @click.option(
        "--region",
        default=app_config.default_region,
        envvar=helpers.ENV_AWS_REGION,
        show_default=True,
    )
    @click.option("--local-port", default=8089, show_default=True)
    def ui_forward_legacy_command(
        stack: str,
        profile: str,
        region: str,
        local_port: int,
    ) -> None:
        """Deprecated: use `ui forward`."""
        ctx = click.get_current_context()
        ctx.invoke(
            ui_forward_command,
            paths="/",
            auth_header=None,
            fetch_token=True,
            stack=stack,
            profile=profile,
            region=region,
            local_port=local_port,
            exec_forward=False,
        )

    cli.add_command(fetch_token_command)
    cli.add_command(run_command)
    cli.add_command(status_command)
    cli.add_command(ui_start_legacy_command)
    cli.add_command(ui_forward_legacy_command)

    return cli
