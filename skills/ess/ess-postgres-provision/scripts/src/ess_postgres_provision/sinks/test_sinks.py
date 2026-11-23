"""Every sink refuses in `check()`, and the file sink never exposes a file."""

import io
import shutil
import stat
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ess_postgres_provision.conftest import RUN_ID
from ess_postgres_provision.exceptions import PreflightError
from ess_postgres_provision.sinks import (
    FileSink,
    Outcome,
    RoleSecret,
    SinkContext,
    TerminalSink,
    build_failed_sinks,
    build_sinks,
    data_directory,
    default_path,
    render_env,
)

_SECRETS = [
    RoleSecret(
        kind="app",
        role="billing_app",
        password="pw-app",
        url="postgresql://billing_app:pw-app@localhost:5432/billing",
    ),
    RoleSecret(
        kind="reader",
        role="billing_reader",
        password="pw-reader",
        url="postgresql://billing_reader:pw-reader@localhost:5432/billing",
    ),
]
_CONTEXT = SinkContext(
    base="billing",
    host="localhost",
    target="localhost:5432",
    run_id=RUN_ID,
    outcome=Outcome.CREATED,
    timestamp=datetime(2026, 11, 19, 12, 0, 5, tzinfo=UTC),
)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _refusal(sink: FileSink | TerminalSink) -> PreflightError:
    with pytest.raises(PreflightError) as raised:
        sink.check()
    assert raised.value.exit_code == 3
    return raised.value


# === File sink: paths ===


def test_default_path_groups_by_host_and_base(private_data_home: Path) -> None:
    assert default_path(_CONTEXT) == (
        private_data_home / "ess-postgres-provision" / "localhost" / "billing.env"
    )


def test_socket_hosts_get_a_flat_directory_name(private_data_home: Path) -> None:
    assert data_directory("/var/run/postgresql") == (
        private_data_home / "ess-postgres-provision" / "socket-var_run_postgresql"
    )


def test_rotated_files_are_timestamped_and_never_collide() -> None:
    rotated = replace(_CONTEXT, outcome=Outcome.ROTATED)
    first = default_path(rotated)
    first.parent.mkdir(parents=True)
    first.touch()

    second = default_path(rotated)

    assert first.name == "billing.rotated-20261119T120005Z.env"
    assert second.name == "billing.rotated-20261119T120005Z-2.env"


# === File sink: refusals ===


def test_refuses_an_existing_file() -> None:
    sink = FileSink(_CONTEXT)
    sink.path.parent.mkdir(parents=True, mode=0o700)
    sink.path.touch()

    assert "is never overwritten" in str(_refusal(sink))


def test_refuses_a_data_directory_other_users_can_read() -> None:
    directory = data_directory("localhost")
    directory.mkdir(parents=True)
    directory.chmod(0o755)

    assert "accessible to other users" in str(_refusal(FileSink(_CONTEXT)))


def test_refuses_an_unwritable_destination(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir(mode=0o500)
    sink = FileSink(replace(_CONTEXT, path=locked / "nested" / "billing.env"))

    try:
        assert "is not writable" in str(_refusal(sink))
    finally:
        locked.chmod(0o700)


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_refuses_a_path_git_would_track_and_accepts_an_ignored_one(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    sink = FileSink(replace(_CONTEXT, path=repo / "billing.env"))

    assert "not ignored" in str(_refusal(sink))
    (repo / ".gitignore").write_text("*.env\n", encoding="utf-8")
    sink.check()


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_relative_sink_path_is_checked_where_it_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    (repo / "secrets").mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    (repo / ".gitignore").write_text("secrets/db.env\n", encoding="utf-8")
    monkeypatch.chdir(repo)
    sink = FileSink(replace(_CONTEXT, path=Path("secrets/db.env")))

    sink.check()


def test_terminal_sink_refuses_without_a_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", io.StringIO())

    assert "needs an interactive terminal" in str(_refusal(TerminalSink(_CONTEXT)))


# === File sink: delivery ===


def test_delivery_writes_a_private_file_in_a_private_directory() -> None:
    sink = FileSink(_CONTEXT)
    sink.check()

    message = sink.deliver(_SECRETS)

    assert message.endswith("ess-postgres-provision/localhost/billing.env")
    assert _mode(sink.path) == 0o600
    assert _mode(sink.path.parent) == 0o700
    assert _mode(sink.path.parent.parent) == 0o700


def test_delivery_never_overwrites_a_file_that_appeared_after_check() -> None:
    sink = FileSink(_CONTEXT)
    sink.check()
    sink.path.parent.mkdir(parents=True, mode=0o700)
    sink.path.write_text("someone else's\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        sink.deliver(_SECRETS)

    assert sink.path.read_text(encoding="utf-8") == "someone else's\n"


def test_env_text_has_a_password_and_url_per_role_and_no_single_database_url() -> None:
    lines = render_env(_CONTEXT, _SECRETS).splitlines()

    assert lines[0] == "# ess-postgres-provision: billing on localhost:5432"
    assert lines[1] == f"# Run {RUN_ID}, created 2026-11-19T12:00:05Z"
    assert lines[2:] == [
        "BILLING_APP_DATABASE_PASSWORD=pw-app",
        "BILLING_APP_DATABASE_URL=postgresql://billing_app:pw-app@localhost:5432/billing",
        "BILLING_READER_DATABASE_PASSWORD=pw-reader",
        "BILLING_READER_DATABASE_URL="
        "postgresql://billing_reader:pw-reader@localhost:5432/billing",
    ]


def test_failed_runs_are_labelled() -> None:
    failed = replace(_CONTEXT, outcome=Outcome.FAILED)

    assert "# FAILED RUN" in render_env(failed, _SECRETS)


# === Registry ===


def test_default_is_one_file_sink() -> None:
    sinks = build_sinks((), (), _CONTEXT)

    assert [type(sink) for sink in sinks] == [FileSink]


def test_sink_paths_replace_the_default_file(tmp_path: Path) -> None:
    paths = (tmp_path / "a.env", tmp_path / "b.env")

    sinks = build_sinks(("file",), paths, _CONTEXT)

    assert [sink.path for sink in sinks] == list(paths)


def test_unknown_sink_is_refused() -> None:
    with pytest.raises(ValueError, match="Unknown sink 'keychain'"):
        build_sinks(("keychain",), (), _CONTEXT)


def test_a_failed_run_without_a_sink_path_writes_to_the_data_directory() -> None:
    sinks = build_failed_sinks(("file", "terminal"), (), _CONTEXT)

    assert [type(sink) for sink in sinks] == [FileSink, TerminalSink]
    assert sinks[0].path.parent == data_directory("localhost")
    assert sinks[0].path.name == "billing.failed-20261119T120005Z.env"


def test_a_failed_run_writes_beside_each_sink_path(tmp_path: Path) -> None:
    paths = (tmp_path / "a" / "chosen.env", tmp_path / "b" / "creds")
    paths[0].parent.mkdir()
    paths[0].touch()

    sinks = build_failed_sinks(("file",), paths, _CONTEXT)

    assert [sink.path for sink in sinks] == [
        tmp_path / "a" / "chosen.failed-20261119T120005Z.env",
        tmp_path / "b" / "creds.failed-20261119T120005Z",
    ]


@pytest.mark.parametrize("chosen", [None, "chosen.env"], ids=["default", "sink path"])
def test_a_failed_file_taken_since_preflight_moves_to_the_next_name(
    tmp_path: Path, chosen: str | None
) -> None:
    path = None if chosen is None else tmp_path / chosen
    (sink,) = build_failed_sinks(("file",), () if path is None else (path,), _CONTEXT)
    sink.check()
    taken = sink.path
    taken.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    taken.write_text("another run's\n", encoding="utf-8")

    sink.check()
    sink.deliver(_SECRETS)

    assert sink.path.parent == taken.parent
    assert sink.path.name.endswith(".failed-20261119T120005Z-2.env")
    assert taken.read_text(encoding="utf-8") == "another run's\n"


def test_a_failed_file_keeps_its_checked_name_while_that_name_is_free(
    tmp_path: Path,
) -> None:
    first = tmp_path / "chosen.failed-20261119T120005Z.env"
    first.touch()
    (sink,) = build_failed_sinks(("file",), (tmp_path / "chosen.env",), _CONTEXT)
    sink.check()
    checked = sink.path
    first.unlink()

    sink.check()

    assert sink.path == checked == tmp_path / "chosen.failed-20261119T120005Z-2.env"
