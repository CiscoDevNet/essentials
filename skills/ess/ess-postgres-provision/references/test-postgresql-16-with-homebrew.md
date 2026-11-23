# Test against PostgreSQL 16 with Homebrew

PostgreSQL 16 is the oldest version `ess-postgres-provision` accepts, because
every membership grant relies on the `WITH SET, INHERIT` options and
`CREATEROLE` rules that 16 introduced. This runs a throwaway 16 server on
macOS next to an existing one, then exercises the tool as each kind of admin.

Commands run from the root of the repo that hosts this skill, with its uv
workspace synced, so `uv run ess-postgres-provision` runs the source. Homebrew's versioned formulas are
keg-only (not linked onto `PATH`), so the steps call them by full path.

## 1. Install and start 16 on port 5433

If another PostgreSQL already listens on 5432, run 16 on 5433 with `pg_ctl`
rather than `brew services`, which would start it on 5432 too:

```bash
brew install postgresql@16
PG16="$(brew --prefix postgresql@16)/bin"
"$PG16/pg_ctl" -D "$(brew --prefix)/var/postgresql@16" -o "-p 5433" -l /tmp/pg16.log start
"$PG16/psql" -h /tmp -p 5433 -d postgres -c 'SELECT version();'
```

Homebrew initializes the data directory with UTF-8 encoding at install time,
so the `template0` encoding check passes. Both servers put their sockets in
`/tmp`; the port keeps them apart. Local authentication defaults to `trust`,
so no step asks for a password.

## 2. Run as a superuser

```bash
uv run ess-postgres-provision --dry-run create smoke16 --host /tmp --port 5433 --admin-user "$USER" --yes
uv run ess-postgres-provision create smoke16 --host /tmp --port 5433 --admin-user "$USER" --yes
uv run ess-postgres-provision verify smoke16 --host /tmp --port 5433 --admin-user "$USER"
uv run ess-postgres-provision teardown smoke16 --host /tmp --port 5433 --admin-user "$USER" --yes
```

`create` should end with every verification check passing. The credentials
go to `~/.local/share/ess-postgres-provision/socket-tmp/smoke16.env`, which
`teardown` leaves in place. Delete it before creating `smoke16` again; the
file sink never overwrites an existing file.

## 3. Run as a managed-service-style admin

A non-superuser admin with `CREATEDB` and `CREATEROLE`, like an RDS master, is
the path that depends most on 16's membership rules:

```bash
"$PG16/psql" -h /tmp -p 5433 -d postgres -c 'CREATE ROLE smoke_prov LOGIN NOSUPERUSER CREATEDB CREATEROLE;'
uv run ess-postgres-provision create smoke16b --host /tmp --port 5433 --admin-user smoke_prov --yes
"$PG16/psql" -h /tmp -p 5433 -d postgres -Atc "SELECT pg_has_role('smoke_prov', 'smoke16b_owner', 'SET');"
uv run ess-postgres-provision teardown smoke16b --host /tmp --port 5433 --admin-user smoke_prov --yes
"$PG16/psql" -h /tmp -p 5433 -d postgres -c 'DROP ROLE smoke_prov;'
```

The `pg_has_role` query must print `f`: after `create`, the admin can manage
the roles but can no longer become the owner.

Repeat the step with `NOINHERIT` added to the `CREATE ROLE`. Both kinds of
admin must get identical results.

## 4. Run the integration tests

```bash
ESS_POSTGRES_PROVISION_TEST_DSN="host=/tmp port=5433 dbname=postgres user=$USER" \
  uv run pytest skills/ess/ess-postgres-provision/scripts
```

## 5. Clean up

```bash
rm -f ~/.local/share/ess-postgres-provision/socket-tmp/smoke16*.env
"$PG16/pg_ctl" -D "$(brew --prefix)/var/postgresql@16" stop
```

To remove 16 entirely, `brew uninstall postgresql@16`, then delete
`$(brew --prefix)/var/postgresql@16`.
