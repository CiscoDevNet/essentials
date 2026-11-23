"""The CLI surface: write safety, argument checks, and exit codes."""

from typing import Any

import pytest
from click.testing import CliRunner

from ess_postgres_provision import __main__ as cli
from ess_postgres_provision.exceptions import (
    DeliveryError,
    PreflightError,
    ProvisioningError,
    Terminated,
    VerificationError,
)
from ess_postgres_provision.ui import Ui

_TARGET = ["--host", "localhost", "--admin-user", "db_provisioner"]


class _FakeCreate:
    """Stands in for `create`: records the `Ui`, prompts unless a dry run."""

    def __init__(self, error: BaseException | None = None) -> None:
        self.calls: list[tuple[Any, Any, Ui]] = []
        self.confirmed = False
        self._error = error

    def __call__(self, _connector: Any, names: Any, options: Any, ui: Ui) -> None:
        self.calls.append((names, options, ui))
        if self._error is not None:
            raise self._error
        if not ui.dry_run:
            ui.confirm("Create?")
            self.confirmed = True


@pytest.fixture
def fake_create(monkeypatch: pytest.MonkeyPatch) -> _FakeCreate:
    fake = _FakeCreate()
    monkeypatch.setattr(cli, "create", fake)
    return fake


def _invoke(*args: str) -> Any:
    return CliRunner().invoke(cli.main, list(args))


def test_dry_run_reaches_the_command_and_needs_no_consent(
    fake_create: _FakeCreate,
) -> None:
    result = _invoke("--dry-run", "create", "billing", *_TARGET)

    assert result.exit_code == 0
    ((names, _options, ui),) = fake_create.calls
    assert names.base == "billing"
    assert ui.dry_run
    assert not fake_create.confirmed


def test_yes_skips_the_prompt_without_a_tty(fake_create: _FakeCreate) -> None:
    result = _invoke("create", "billing", *_TARGET, "--yes")

    assert result.exit_code == 0
    assert fake_create.confirmed


def test_a_write_without_a_tty_or_yes_is_refused(fake_create: _FakeCreate) -> None:
    result = _invoke("create", "billing", *_TARGET)

    assert result.exit_code == 2
    assert "pass --yes" in result.stderr
    assert not fake_create.confirmed


def test_dry_run_wins_over_yes(fake_create: _FakeCreate) -> None:
    result = _invoke("--dry-run", "create", "billing", *_TARGET, "--yes")

    assert result.exit_code == 0
    assert fake_create.calls[0][2].dry_run
    assert not fake_create.confirmed


def test_options_reach_the_command(fake_create: _FakeCreate) -> None:
    _invoke(
        "create",
        "billing",
        *_TARGET,
        "--yes",
        "--extension",
        "pg_trgm",
        "--digits",
        "6",
        "--no-reader-read-only",
        "--reader-statement-timeout",
        "0",
    )
    options = fake_create.calls[0][1]

    assert options.extensions == ("pg_trgm",)
    assert options.delivery.digits == 6
    assert not options.guards.read_only
    assert options.guards.statement_timeout is None
    assert options.guards.idle_in_transaction_timeout == "60s"


@pytest.mark.parametrize(
    "args",
    [
        ["create", "Billing", *_TARGET],
        ["create", "pg_billing", *_TARGET],
        ["create", "billing", *_TARGET, "--digits", "3"],
        ["create", "billing", "--host", "localhost"],
        ["create", "billing", *_TARGET, "--sink", "keychain"],
        ["rotate", "billing", *_TARGET, "--role", "admin"],
    ],
    ids=["uppercase", "pg prefix", "few digits", "no admin", "bad sink", "bad role"],
)
def test_usage_errors_exit_2_before_connecting(
    fake_create: _FakeCreate, args: list[str]
) -> None:
    result = _invoke(*args)

    assert result.exit_code == 2
    assert fake_create.calls == []


@pytest.mark.parametrize(
    ("error", "exit_code"),
    [
        (PreflightError("refused"), 3),
        (ProvisioningError("failed"), 1),
        (VerificationError("mismatch"), 1),
        (DeliveryError("lost"), 4),
        (Terminated(), 143),
    ],
    ids=["preflight", "provisioning", "verification", "delivery", "sigterm"],
)
def test_domain_errors_map_to_their_exit_codes(
    monkeypatch: pytest.MonkeyPatch, error: BaseException, exit_code: int
) -> None:
    monkeypatch.setattr(cli, "create", _FakeCreate(error))

    result = _invoke("create", "billing", *_TARGET, "--yes")

    assert result.exit_code == exit_code


def test_verify_offers_no_dry_run_or_yes() -> None:
    result = _invoke("verify", "billing", *_TARGET, "--yes")

    assert result.exit_code == 2
    assert "no such option" in result.stderr.lower()
