"""Where new credentials go."""

from .base import (
    Outcome,
    RoleSecret,
    SecretSink,
    SinkContext,
    env_names,
    render_env,
)
from .delivery import DeliveryReport, deliver
from .file import FileSink, data_directory, default_path, display_path
from .registry import (
    DEFAULT_SINK,
    SINK_FACTORIES,
    build_failed_sinks,
    build_sinks,
    describe,
    fallback_sink,
)
from .terminal import TerminalSink

__all__ = [
    "DEFAULT_SINK",
    "SINK_FACTORIES",
    "DeliveryReport",
    "FileSink",
    "Outcome",
    "RoleSecret",
    "SecretSink",
    "SinkContext",
    "TerminalSink",
    "build_failed_sinks",
    "build_sinks",
    "data_directory",
    "default_path",
    "deliver",
    "describe",
    "display_path",
    "env_names",
    "fallback_sink",
    "render_env",
]
