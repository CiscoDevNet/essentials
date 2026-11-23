"""Sink names and the factories that build them.

Adding a sink, such as a keychain or a password manager, is one module and
one entry in `SINK_FACTORIES`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

from .base import Outcome, SecretSink, SinkContext
from .file import FileSink, display_path
from .terminal import TerminalSink

DEFAULT_SINK = "file"

SINK_FACTORIES: dict[str, Callable[[SinkContext], SecretSink]] = {
    "file": FileSink,
    "terminal": TerminalSink,
}


def build_sinks(
    names: Sequence[str], paths: Sequence[Path], context: SinkContext
) -> list[SecretSink]:
    """The sinks for one run.

    Args:
        names: `--sink` values. Defaults to the file sink.
        paths: `--sink-path` values. Each one is a file sink of its own.
        context: The run being delivered.

    Raises:
        ValueError: A name has no factory.
    """
    selected = list(dict.fromkeys(names)) or [DEFAULT_SINK]
    unknown = [name for name in selected if name not in SINK_FACTORIES]
    if unknown:
        msg = (
            f"Unknown sink {unknown[0]!r}; expected one of {', '.join(SINK_FACTORIES)}."
        )
        raise ValueError(msg)

    sinks: list[SecretSink] = [FileSink(replace(context, path=path)) for path in paths]
    for name in selected:
        if name == "file" and paths:
            continue
        sinks.append(SINK_FACTORIES[name](context))
    return sinks


def build_failed_sinks(
    names: Sequence[str], paths: Sequence[Path], context: SinkContext
) -> list[SecretSink]:
    """The sinks for a failed run: `failed` files, plus any non-file sinks.

    Each `--sink-path` gets a `failed` file beside it. Without one, a single
    `failed` file goes in the data directory.
    """
    failed = replace(context, outcome=Outcome.FAILED, path=None)
    sinks: list[SecretSink] = [
        FileSink(replace(failed, path=path)) for path in paths
    ] or [FileSink(failed)]
    sinks.extend(
        SINK_FACTORIES[name](failed)
        for name in dict.fromkeys(names)
        if name != "file" and name in SINK_FACTORIES
    )
    return sinks


def describe(sinks: Sequence[SecretSink]) -> str:
    """Where the credentials will go, for the header: paths for files, else names."""
    return ", ".join(
        display_path(sink.path) if isinstance(sink, FileSink) else sink.name
        for sink in sinks
    )


def fallback_sink(context: SinkContext) -> SecretSink:
    """A new `failed` file in the data directory, for when a sink fails."""
    return FileSink(replace(context, outcome=Outcome.FAILED, path=None))
