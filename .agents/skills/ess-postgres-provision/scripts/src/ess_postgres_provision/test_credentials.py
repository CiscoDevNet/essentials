"""Credentials are delivered once they may be live, whatever happens next."""

import logging
import os
import signal
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ess_postgres_provision.conftest import RUN_ID
from ess_postgres_provision.credentials import Delivery, LiveFlag, run_and_deliver
from ess_postgres_provision.exceptions import (
    DeliveryError,
    InterruptedRunError,
    ProvisioningError,
    VerificationError,
)
from ess_postgres_provision.sinks import (
    Outcome,
    RoleSecret,
    SinkContext,
    build_failed_sinks,
    data_directory,
)

_SECRETS = [
    RoleSecret(
        kind="app",
        role="billing_app",
        password="correct-horse-battery-staple-1234",
        url="postgresql://billing_app:x@localhost:5432/billing",
    )
]
_CONTEXT = SinkContext(
    base="billing",
    host="localhost",
    target="localhost:5432",
    run_id=RUN_ID,
    outcome=Outcome.CREATED,
    timestamp=datetime(2026, 11, 19, 12, 0, tzinfo=UTC),
)
_RECOVERY = "ess-postgres-provision teardown billing, then rerun create"


class _RecordingSink:
    name = "recording"

    def __init__(self, error: Exception | None = None) -> None:
        self.received: list[Sequence[RoleSecret]] = []
        self._error = error

    def check(self) -> None:
        """Always ready."""

    def deliver(self, secrets: Sequence[RoleSecret]) -> str:
        if self._error is not None:
            raise self._error
        self.received.append(secrets)
        return "Delivered to the recording sink"


def _run(
    work: Callable[[LiveFlag], None],
    sink: _RecordingSink,
    sink_paths: Sequence[Path] = (),
) -> object:
    return run_and_deliver(
        work,
        _SECRETS,
        Delivery(
            [sink],
            build_failed_sinks((), sink_paths, _CONTEXT),
            _CONTEXT,
            _RECOVERY,
        ),
    )


def _failed_files() -> list[Path]:
    return sorted(data_directory("localhost").glob("billing.failed-*.env"))


def _mark_then(error: BaseException) -> Callable[[LiveFlag], None]:
    def work(flag: LiveFlag) -> None:
        flag.mark()
        raise error

    return work


def test_success_delivers_to_the_configured_sinks() -> None:
    sink = _RecordingSink()

    report = _run(lambda _flag: None, sink)

    assert sink.received == [_SECRETS]
    assert report.messages == ["Delivered to the recording sink"]
    assert _failed_files() == []


def test_failure_before_anything_is_live_delivers_nothing() -> None:
    sink = _RecordingSink()
    error = ProvisioningError("preflight-like failure")

    def work(_flag: LiveFlag) -> None:
        raise error

    with pytest.raises(ProvisioningError) as raised:
        _run(work, sink)

    assert raised.value is error
    assert sink.received == []
    assert _failed_files() == []


def test_failure_after_commit_delivers_a_failed_file_and_exits_1() -> None:
    sink = _RecordingSink()

    with pytest.raises(ProvisioningError) as raised:
        _run(_mark_then(ProvisioningError("Step 'create schema' failed")), sink)

    (failed,) = _failed_files()
    content = failed.read_text(encoding="utf-8")
    assert raised.value.exit_code == 1
    assert "Step 'create schema' failed" in str(raised.value)
    assert f"Recover with: {_RECOVERY}" in str(raised.value)
    assert failed.name in str(raised.value)
    assert "# FAILED RUN" in content
    assert "BILLING_APP_DATABASE_PASSWORD=correct-horse-battery-staple-1234" in content
    assert sink.received == []


def test_failure_after_commit_writes_beside_the_sink_path_not_the_data_directory(
    tmp_path: Path,
) -> None:
    data_directory("localhost").mkdir(parents=True, mode=0o755)
    data_directory("localhost").chmod(0o755)
    chosen = tmp_path / "secure" / "billing.env"

    with pytest.raises(ProvisioningError) as raised:
        _run(_mark_then(ProvisioningError("boom")), _RecordingSink(), (chosen,))

    (failed,) = chosen.parent.glob("billing.failed-*.env")
    assert failed.name in str(raised.value)
    assert "BILLING_APP_DATABASE_PASSWORD=" in failed.read_text(encoding="utf-8")
    assert _failed_files() == []


def test_verification_failure_keeps_its_type() -> None:
    with pytest.raises(VerificationError) as raised:
        _run(_mark_then(VerificationError("schema privileges")), _RecordingSink())

    assert raised.value.exit_code == 1
    assert len(_failed_files()) == 1


def test_keyboard_interrupt_after_commit_delivers_and_exits_130() -> None:
    with pytest.raises(InterruptedRunError) as raised:
        _run(_mark_then(KeyboardInterrupt()), _RecordingSink())

    assert raised.value.exit_code == 130
    assert str(raised.value).startswith("Interrupted")
    assert len(_failed_files()) == 1


def test_sigterm_after_commit_delivers_and_exits_143() -> None:
    def work(flag: LiveFlag) -> None:
        flag.mark()
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(5)

    previous = signal.getsignal(signal.SIGTERM)
    with pytest.raises(InterruptedRunError) as raised:
        _run(work, _RecordingSink())

    assert raised.value.exit_code == 143
    assert len(_failed_files()) == 1
    assert signal.getsignal(signal.SIGTERM) is previous


def test_a_failed_sink_falls_back_to_a_failed_file() -> None:
    sink = _RecordingSink(error=OSError("keychain locked"))

    report = _run(lambda _flag: None, sink)

    assert report.failures == ["recording: keychain locked"]
    assert len(report.messages) == 1
    assert len(_failed_files()) == 1


def test_every_sink_failing_exits_4_even_after_commit() -> None:
    directory = data_directory("localhost")
    directory.mkdir(parents=True, mode=0o755)
    directory.chmod(0o755)
    sink = _RecordingSink(error=OSError("keychain locked"))

    with pytest.raises(DeliveryError) as raised:
        _run(lambda _flag: None, sink)

    assert raised.value.exit_code == 4
    assert "run rotate" in str(raised.value)


def test_no_password_reaches_the_log(caplog: pytest.LogCaptureFixture) -> None:
    sink = _RecordingSink(error=OSError("keychain locked"))

    with caplog.at_level(logging.DEBUG):
        _run(lambda _flag: None, sink)
        with pytest.raises(ProvisioningError):
            _run(_mark_then(ProvisioningError("boom")), sink)

    assert caplog.records
    assert _SECRETS[0].password not in caplog.text


def test_secrets_never_appear_in_a_repr() -> None:
    assert _SECRETS[0].password not in repr(_SECRETS[0])
    assert "billing_app:x@" not in repr(_SECRETS[0])
