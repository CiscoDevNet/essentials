"""Base name validation and the names and markers derived from it."""

import pytest

from ess_postgres_provision.conftest import RUN_ID
from ess_postgres_provision.exceptions import InvalidNameError
from ess_postgres_provision.naming import derive_names

_MAX_IDENTIFIER_BYTES = 63


def test_every_name_derives_from_the_base() -> None:
    names = derive_names("billing")

    assert (names.database, names.schema) == ("billing", "billing")
    assert names.roles == (
        "billing_owner",
        "billing_migrations",
        "billing_app",
        "billing_reader",
    )


def test_the_longest_base_keeps_every_role_under_the_identifier_limit() -> None:
    names = derive_names("a" * 41)

    assert max(len(role.encode()) for role in names.roles) <= _MAX_IDENTIFIER_BYTES


@pytest.mark.parametrize(
    "base",
    ["", "Billing", "1billing", "billing-app", "a" * 42, "bïlling", "billing\n"],
    ids=[
        "empty",
        "uppercase",
        "digit first",
        "hyphen",
        "too long",
        "non-ascii",
        "trailing newline",
    ],
)
def test_names_outside_the_pattern_are_refused(base: str) -> None:
    with pytest.raises(InvalidNameError, match="not a valid base name"):
        derive_names(base)


@pytest.mark.parametrize("base", ["public", "postgres", "template1", "pg_billing"])
def test_reserved_names_are_refused(base: str) -> None:
    with pytest.raises(InvalidNameError, match="reserved"):
        derive_names(base)


def test_marker_round_trips_its_run_id() -> None:
    names = derive_names("billing")

    assert names.run_id_from_marker(names.marker(RUN_ID)) == RUN_ID


@pytest.mark.parametrize(
    "comment",
    [
        None,
        "made by hand",
        f"ess-postgres-provision:billing_x:{RUN_ID}",
        "ess-postgres-provision:billing:not-a-run-id",
        f"ess-postgres-provision:billing:{RUN_ID}:extra",
        f"ess-postgres-provision:billing:{RUN_ID}\n",
    ],
    ids=[
        "none",
        "other text",
        "other base",
        "bad run id",
        "trailing text",
        "trailing newline",
    ],
)
def test_anything_but_this_bases_marker_has_no_run_id(comment: str | None) -> None:
    assert derive_names("billing").run_id_from_marker(comment) is None


def test_kind_of_rejects_a_role_from_another_base() -> None:
    with pytest.raises(ValueError, match="not a role derived from 'billing'"):
        derive_names("billing").kind_of("payroll_app")
