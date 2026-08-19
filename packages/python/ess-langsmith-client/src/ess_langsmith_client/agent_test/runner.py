"""Conversation runner for LangGraph agent smoke tests."""

import json
import os

import click

_AGENT_TEST_EXTRA = "ess-langsmith-client[agent-test]"


def _get_sync_client():
    try:
        from langgraph_sdk import get_sync_client  # noqa: PLC0415  # optional extra
    except ImportError as exc:
        raise click.ClickException(
            f"langgraph-sdk is required for agent tests. "
            f"Install with: uv add --dev {_AGENT_TEST_EXTRA}"
        ) from exc
    return get_sync_client


def list_assistants(client) -> None:
    click.echo("\nAvailable assistants:")
    try:
        assistants = client.assistants.search()
        for assistant in assistants:
            graph_id = assistant.get("graph_id", "N/A")
            name = assistant.get("name", graph_id)
            click.echo(f"  - {name} (graph_id={graph_id})")
    except Exception as exc:
        click.echo(
            click.style(f"  Warning: Could not list assistants: {exc}", fg="yellow")
        )


def _handle_streaming_response(
    client, thread_id: str, assistant_id: str, message: str
) -> None:
    click.echo("--- Streaming response ---")
    input_data = {"messages": [{"role": "user", "content": message}]}
    for event in client.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        input=input_data,
    ):
        if hasattr(event, "data") and event.data:
            messages = event.data.get("messages", [])
            for msg in messages:
                if msg.get("type") == "ai" or msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    if content:
                        click.echo(content)
    click.echo("--- End of stream ---")


def _handle_non_streaming_response(
    client, thread_id: str, assistant_id: str, message: str
) -> None:
    input_data = {"messages": [{"role": "user", "content": message}]}
    result = client.runs.wait(
        thread_id=thread_id,
        assistant_id=assistant_id,
        input=input_data,
    )
    messages = result.get("messages", [])
    if messages:
        click.echo("--- Response ---")
        for msg in messages:
            role = msg.get("type", msg.get("role", "unknown"))
            content = msg.get("content", "")
            if content:
                click.echo(f"[{role}] {content}")
        click.echo("--- End ---")
    else:
        click.echo("Raw result:")
        click.echo(json.dumps(result, indent=2, default=str))


def run_conversation(
    base_url: str,
    assistant_id: str,
    message: str,
    *,
    use_stream: bool,
    api_key: str | None = None,
) -> str:
    """Connect to an agent, send a message, and return the thread ID."""
    get_sync_client = _get_sync_client()
    client = get_sync_client(
        url=base_url,
        api_key=api_key or os.environ.get("LANGSMITH_API_KEY"),
    )
    list_assistants(client)

    click.echo("\nCreating thread and sending message...")
    click.echo(f"  Assistant: {assistant_id}")
    click.echo(f"  Message: {message}")
    click.echo()

    thread = client.threads.create()
    thread_id = thread["thread_id"]

    if use_stream:
        _handle_streaming_response(client, thread_id, assistant_id, message)
    else:
        _handle_non_streaming_response(client, thread_id, assistant_id, message)

    click.echo(f"\nThread ID: {thread_id}")
    click.echo(click.style("Test complete!", fg="green"))
    return thread_id
