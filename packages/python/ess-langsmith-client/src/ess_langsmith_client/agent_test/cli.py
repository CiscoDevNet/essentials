"""Click CLI builders for deployed and local agent smoke tests."""

import socket
import urllib.parse

import click

from ess_langsmith_client.agent_test.resolution import resolve_base_url
from ess_langsmith_client.agent_test.runner import run_conversation

_DEFAULT_LOCAL_URL = "http://127.0.0.1:2024"


def _server_is_reachable(url: str) -> bool:
    """Check if the server is accepting connections."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def build_test_command(
    service: str,
    *,
    default_message: str = "Hello! What can you do?",
    default_assistant_id: str = "agent",
) -> click.Command:
    """Build a Click command for testing a deployed LangGraph agent."""

    @click.command()
    @click.option(
        "--deployment",
        "-d",
        default=None,
        help=(
            f"Deployment name to resolve via the control plane "
            f"(default: <{service}>-<env>). Ignored if --prefix/--kubectl is set."
        ),
    )
    @click.option(
        "--env",
        "-e",
        default=None,
        help="Environment for canonical deployment name (default: $APP_ENV or dev).",
    )
    @click.option(
        "--region",
        type=click.Choice(["us", "eu"]),
        default="us",
        show_default=True,
        help="LangSmith Control Plane region (us or eu).",
    )
    @click.option(
        "--url",
        default=None,
        help=(
            "Friendly ingress host for control-plane resolution "
            "(e.g. https://agents.example.com), or base URL for "
            "--prefix/--kubectl (default: http://localhost:8000 when prefix/kubectl)."
        ),
    )
    @click.option(
        "--prefix",
        default=None,
        help="Mount prefix (e.g. /lgp/<hash>) joined onto --url. Skips resolution.",
    )
    @click.option(
        "--kubectl",
        "use_kubectl",
        is_flag=True,
        help="Auto-detect the mount prefix from a running pod via kubectl, onto --url.",
    )
    @click.option(
        "--assistant-id",
        default=default_assistant_id,
        help=f"Assistant/graph ID to invoke (default: {default_assistant_id})",
    )
    @click.option(
        "--message",
        "-m",
        default=default_message,
        help="Message to send to the agent",
    )
    @click.option(
        "--stream",
        "use_stream",
        is_flag=True,
        help="Stream the response instead of waiting for completion",
    )
    def test(  # noqa: PLR0913  # Click injects one param per option
        deployment: str | None,
        env: str | None,
        region: str,
        url: str | None,
        prefix: str | None,
        use_kubectl: bool,
        assistant_id: str,
        message: str,
        use_stream: bool,
    ):
        """Test a deployed LangGraph agent.

        \b
        Examples:
            # Resolve the nice URL from the control plane (default)
            uv run python tools/test_deployed.py --deployment {service}-prod-dev
            # Same deployment, friendly dev ingress host
            uv run python tools/test_deployed.py \\
                --url https://agents.example.com -d {service}-prod-dev
            # Canonical name from project + env
            uv run python tools/test_deployed.py --env prod -m "What is 2+2?"
            # Manual prefix (port-forward)
            uv run python tools/test_deployed.py --prefix /lgp/abc
            # kubectl auto-detect (legacy port-forward flow)
            uv run python tools/test_deployed.py --kubectl
            # Stream the response
            uv run python tools/test_deployed.py -d {service}-prod-dev --stream
        """.format(service=service)
        base_url = resolve_base_url(
            service,
            url=url,
            prefix=prefix,
            use_kubectl=use_kubectl,
            deployment=deployment,
            env=env,
            region=region,
        )
        click.echo(f"Connecting to {base_url}")
        run_conversation(
            base_url,
            assistant_id,
            message,
            use_stream=use_stream,
        )

    return test


def build_local_test_command(
    service: str,  # pylint: disable=unused-argument  # per-app shim identity
    *,
    default_message: str = "Hello!",
    default_assistant_id: str = "agent",
    default_url: str = _DEFAULT_LOCAL_URL,
) -> click.Command:
    """Build a Click command for testing a local LangGraph dev server."""

    @click.command()
    @click.option(
        "--url",
        default=default_url,
        help=f"Local LangGraph dev server URL (default: {default_url})",
    )
    @click.option(
        "--assistant-id",
        default=default_assistant_id,
        help=f"Assistant/graph ID to invoke (default: {default_assistant_id})",
    )
    @click.option(
        "--message",
        "-m",
        default=default_message,
        help=f'Message to send to the agent (default: "{default_message}")',
    )
    @click.option(
        "--stream",
        "use_stream",
        is_flag=True,
        help="Stream the response instead of waiting for completion",
    )
    def test(url: str, assistant_id: str, message: str, use_stream: bool):
        """Test the agent running locally via ``langgraph dev``.

        \b
        Examples:
            uv run python tools/test_local.py
            uv run python tools/test_local.py -m "What is 2+2?"
            uv run python tools/test_local.py --stream
            uv run python tools/test_local.py --url http://127.0.0.1:8123
        """
        if not _server_is_reachable(url):
            raise click.ClickException(
                f"Cannot reach server at {url}. "
                "Start the local server first: uv run langgraph dev"
            )

        click.echo(f"Connecting to {url}")
        run_conversation(
            url,
            assistant_id,
            message,
            use_stream=use_stream,
            api_key=None,
        )

    return test


@click.command()
@click.option("--service", required=True, help="Service name for control-plane lookup.")
@click.option("--deployment", "-d", default=None, help="Explicit deployment name.")
@click.option("--env", "-e", default=None, help="Environment for canonical name.")
@click.option(
    "--region",
    type=click.Choice(["us", "eu"]),
    default="us",
    show_default=True,
    help="LangSmith Control Plane region (us or eu).",
)
@click.option(
    "--url",
    default=None,
    help="Friendly ingress host or port-forward base URL.",
)
@click.option("--prefix", default=None)
@click.option("--kubectl", "use_kubectl", is_flag=True)
@click.option("--assistant-id", default="agent")
@click.option("--message", "-m", default="Hello! What can you do?")
@click.option("--stream", "use_stream", is_flag=True)
def deployed(  # noqa: PLR0913  # Click injects one param per option
    service: str,
    deployment: str | None,
    env: str | None,
    region: str,
    url: str | None,
    prefix: str | None,
    use_kubectl: bool,
    assistant_id: str,
    message: str,
    use_stream: bool,
) -> None:
    """Console entry point: test a deployed agent by service name."""
    base_url = resolve_base_url(
        service,
        url=url,
        prefix=prefix,
        use_kubectl=use_kubectl,
        deployment=deployment,
        env=env,
        region=region,
    )
    click.echo(f"Connecting to {base_url}")
    run_conversation(
        base_url,
        assistant_id,
        message,
        use_stream=use_stream,
    )
