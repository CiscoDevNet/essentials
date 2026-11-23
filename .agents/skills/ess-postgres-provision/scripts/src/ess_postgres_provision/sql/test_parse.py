"""Every statement the tool can send parses with PostgreSQL's own parser."""

import re

import pglast
import pytest
from psycopg import sql

from ess_postgres_provision.naming import ROLE_KINDS, derive_names
from ess_postgres_provision.sql import Statement, catalog
from ess_postgres_provision.sql.database import (
    Extension,
    ReaderGuards,
    database_statements,
)
from ess_postgres_provision.sql.lifecycle import (
    allow_connections,
    drop_database,
    drop_roles,
    regrant_owner,
    restore_statements,
    rotate_statements,
)
from ess_postgres_provision.sql.maintenance import (
    connect_statements,
    create_database_statement,
    revoke_owner_from_admin,
    role_statements,
)

_NAMES = derive_names("billing")
_ADMIN = "db_provisioner"
_RUN_ID = "0" * 32
_VERIFIER = "SCRAM-SHA-256$4096:c2FsdA==$c3RvcmVkS2V5:c2VydmVyS2V5"
_VERIFIERS = dict.fromkeys(ROLE_KINDS, _VERIFIER)
_EXTENSIONS = [Extension("pg_trgm", trusted=True), Extension("vector", trusted=False)]
_NAMED_PLACEHOLDER = re.compile(r"%\(\w+\)s")


def _write_statements() -> list[Statement]:
    return [
        *role_statements(_NAMES, _VERIFIERS, _RUN_ID, _ADMIN),
        create_database_statement(_NAMES),
        *connect_statements(_NAMES, _ADMIN),
        *database_statements(_NAMES, _EXTENSIONS, ReaderGuards()),
        revoke_owner_from_admin(_NAMES, _ADMIN),
        *rotate_statements(_NAMES, _VERIFIERS),
        regrant_owner(_NAMES, _ADMIN),
        allow_connections(_NAMES, allowed=False),
        allow_connections(_NAMES, allowed=True),
        drop_database(_NAMES),
        *drop_roles(list(_NAMES.roles)),
        *restore_statements(_NAMES, _ADMIN),
    ]


def _composables() -> list[tuple[str, sql.Composable]]:
    found: list[tuple[str, sql.Composable]] = []
    for statement in _write_statements():
        found.append((statement.purpose, statement.query))
        if statement.display is not None:
            found.append((f"{statement.purpose} (display)", statement.display))
        if statement.only_if is not None:
            found.append((f"{statement.purpose} (only if)", statement.only_if))
    return found


_COMPOSABLES = dict(_composables())
_CATALOG_QUERIES = {
    name: value for name, value in vars(catalog).items() if name.isupper()
}


@pytest.mark.parametrize("composable", _COMPOSABLES.values(), ids=_COMPOSABLES)
def test_write_statement_parses(composable: sql.Composable) -> None:
    assert len(pglast.parse_sql(composable.as_string())) == 1


@pytest.mark.parametrize("query", _CATALOG_QUERIES.values(), ids=_CATALOG_QUERIES)
def test_catalog_query_parses(query: str) -> None:
    assert len(pglast.parse_sql(_NAMED_PLACEHOLDER.sub("NULL", query))) == 1


@pytest.mark.parametrize("query", _CATALOG_QUERIES.values(), ids=_CATALOG_QUERIES)
def test_catalog_query_uses_named_placeholders(query: str) -> None:
    assert "%s" not in query


@pytest.mark.parametrize(
    "condition", ["", "WHERE NOT (srid BETWEEN 2000 AND 6999)"], ids=["all", "filter"]
)
def test_config_table_query_parses(condition: str) -> None:
    query = catalog.config_table_has_rows("public", "spatial_ref_sys", condition)

    assert len(pglast.parse_sql(query.as_string())) == 1
