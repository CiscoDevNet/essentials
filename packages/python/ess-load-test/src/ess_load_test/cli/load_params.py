"""Shared Locust load-test parameters for CLI and SSM runner."""

# pylint: disable=too-many-arguments,too-many-positional-arguments

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import click

ENV_USERS = "LOAD_TEST_USERS"
ENV_SPAWN_RATE = "LOAD_TEST_SPAWN_RATE"
ENV_DURATION = "LOAD_TEST_DURATION"


@dataclass(frozen=True)
class LoadTestParams:
    """Locust user count, spawn rate, and optional run controls."""

    users: int = 50
    spawn_rate: float = 5.0
    duration: str | None = None
    user_classes: tuple[str, ...] = ()
    autostart: bool = False
    autoquit: int | None = None
    csv_prefix: str | None = None
    html_path: str | None = None
    reset_stats: bool = False


def config_users_json(user_classes: tuple[str, ...]) -> str | None:
    """Build Locust --config-users JSON from user class names."""
    if not user_classes:
        return None
    configs = [{"user_class_name": name} for name in user_classes]
    return json.dumps(configs)


def build_locust_load_flag_lines(
    params: LoadTestParams,
    *,
    headless: bool,
    shell_quote: Callable[[str], str],
) -> list[str]:
    """Return Locust CLI flag lines for master command assembly."""
    lines = [
        f"-u {params.users}",
        f"-r {params.spawn_rate}",
    ]
    if params.duration is not None:
        lines.append(f"-t {shell_quote(params.duration)}")
    config_users = config_users_json(params.user_classes)
    if config_users is not None:
        lines.append(f"--config-users {shell_quote(config_users)}")
    if headless:
        lines.append("--headless")
    elif params.autostart:
        lines.append("--autostart")
        if params.autoquit is not None:
            lines.append(f"--autoquit {params.autoquit}")
    if headless:
        if params.csv_prefix is not None:
            lines.append(f"--csv {shell_quote(params.csv_prefix)}")
        if params.html_path is not None:
            lines.append(f"--html {shell_quote(params.html_path)}")
        if params.reset_stats:
            lines.append("--reset-stats")
    return lines


def load_test_params_from_click(  # noqa: PLR0913
    *,
    users: int,
    spawn_rate: float,
    duration: str | None,
    user_class: tuple[str, ...],
    autostart: bool,
    autoquit: int | None,
    csv_prefix: str | None = None,
    html_path: str | None = None,
    reset_stats: bool = False,
) -> LoadTestParams:
    """Build LoadTestParams from Click option values."""
    return LoadTestParams(
        users=users,
        spawn_rate=spawn_rate,
        duration=duration,
        user_classes=user_class,
        autostart=autostart,
        autoquit=autoquit,
        csv_prefix=csv_prefix,
        html_path=html_path,
        reset_stats=reset_stats,
    )


def load_test_params_options(*, duration_default: str | None, headless_exports: bool):
    """Decorator factory for shared Locust load-test CLI options."""

    def decorator(func: Any) -> Any:
        func = click.option(
            "--users",
            "-u",
            default=50,
            show_default=True,
            envvar=ENV_USERS,
            help="Peak number of concurrent Locust users.",
        )(func)
        func = click.option(
            "--spawn-rate",
            "-r",
            default=5.0,
            show_default=True,
            envvar=ENV_SPAWN_RATE,
            help="Users spawned per second.",
        )(func)
        duration_help = (
            "Test duration (Locust time format, e.g. 5m, 30s). "
            "Headless runs require a duration; UI runs pre-fill when set."
        )
        if duration_default is None:
            func = click.option(
                "--duration",
                "-t",
                default=None,
                envvar=ENV_DURATION,
                help=duration_help,
            )(func)
        else:
            func = click.option(
                "--duration",
                "-t",
                default=duration_default,
                show_default=True,
                envvar=ENV_DURATION,
                help=duration_help,
            )(func)
        func = click.option(
            "--user-class",
            "user_class",
            multiple=True,
            help="Locust user class to include (repeatable). Default: all.",
        )(func)
        func = click.option(
            "--autostart",
            is_flag=True,
            default=False,
            help="Start swarming immediately when workers connect (UI mode only).",
        )(func)
        func = click.option(
            "--autoquit",
            type=int,
            default=None,
            help="Quit Locust N seconds after the run finishes (requires --autostart).",
        )(func)
        if headless_exports:
            func = click.option(
                "--csv",
                "csv_prefix",
                default=None,
                help="Write CSV stats to this path prefix (headless run only).",
            )(func)
            func = click.option(
                "--html",
                "html_path",
                default=None,
                help="Write HTML report to this path (headless run only).",
            )(func)
            func = click.option(
                "--reset-stats",
                is_flag=True,
                default=False,
                help="Reset statistics after spawn completes (headless run only).",
            )(func)
        return func

    return decorator
