# ess-postgres-provision CLI reference

Give it a base name, get a Postgres database, a dedicated schema, and four
separated login roles with generated passwords, verified before it reports
success. Works for Django or any other app that keeps its data in Postgres.

```bash
$ ess-postgres-provision --dry-run create billing \
    --host db.example.com --admin-user db_provisioner
Connecting as:   db_provisioner  (superuser: no, createdb: yes, createrole: yes)
Target:          billing @ db.example.com:5432  (SSL: TLSv1.3)
Will create:     billing_owner, billing_migrations, billing_app, billing_reader
Credentials to:  ~/.local/share/ess-postgres-provision/db.example.com/billing.env
-- Connected to postgres as db_provisioner
BEGIN;
CREATE ROLE "billing_owner" LOGIN NOSUPERUSER ... PASSWORD '***';
...

$ ess-postgres-provision create billing \
    --host db.example.com --admin-user db_provisioner
...
Credentials written to ~/.local/share/ess-postgres-provision/db.example.com/billing.env
```

| Role | Can |
| --- | --- |
| `billing_owner` | Own the database and schema. The project's admin credential, not a cluster superuser. |
| `billing_migrations` | Create, alter, and drop tables in schema `billing`. Point migrations here. |
| `billing_app` | Read and write rows, use sequences, call migrations' functions. No `CREATE`, no `TRUNCATE`. Point the app here. |
| `billing_reader` | Read rows. Defaults to read-only transactions with idle and statement timeouts. |

None of the four is `SUPERUSER`, `CREATEDB`, `CREATEROLE`, `REPLICATION`, or
`BYPASSRLS`. Every role's `search_path` is `billing, public` in this database
only, so the application needs no settings change.

## Running the CLI

The CLI ships in this skill's `scripts/` directory. Install the skill with
APM, which also installs the `ess-passwords` skill beside it; the CLI takes
its password generator from there. Then run it with uv, where `SKILL_DIR`
is this skill's installed directory:

```bash
uvx --from "$SKILL_DIR/scripts" ess-postgres-provision --help
```

uv builds the CLI into its own cache, so nothing is written inside the
skill. If uv reports `Distribution not found` for `ess-passwords`, the
sibling skill is missing: reinstall with `apm install`, not a manual copy.

Requires uv and PostgreSQL 16 or later. Any server where the admin has `CREATEDB`
and `CREATEROLE` should work, local or managed. Tested on local PostgreSQL 16
and 17 and Amazon RDS for PostgreSQL 17; Aurora, Azure Database for
PostgreSQL, and Cloud SQL are untested.

## Usage

`--dry-run` goes before the subcommand and applies to every write. A dry run
runs every check and prints the SQL with each password verifier shown as
`'***'`. The writes (`create`, `rotate`, `teardown`) prompt for
confirmation; `--yes` skips the prompt, and without a terminal it is
required.

### `ess-postgres-provision create BASE_NAME`

Creates the database and schema `BASE_NAME` and roles `BASE_NAME_owner`,
`_migrations`, `_app`, and `_reader`. It verifies the result by logging in as
each role, then delivers the passwords.

`BASE_NAME` is 1 to 41 lowercase letters, digits, and underscores, starting
with a letter. It may not be `public`, `postgres`, `template0`, `template1`,
or `information_schema`, or start with `pg_`.

| Flag | Default | Description |
| --- | --- | --- |
| `--host` | required | Server host, IP, or Unix socket directory |
| `--port` | `5432` | Server port |
| `--admin-user` | required | A superuser, or a role with `CREATEDB` and `CREATEROLE` (an RDS master qualifies). Its password comes from `PGPASSWORD`, `~/.pgpass`, or a prompt, never a flag |
| `--allow-insecure` | off | Allow a non-local host without SSL. Without it, a non-local connection requires SSL before it authenticates: `PGSSLMODE` is used when it is `require`, `verify-ca`, or `verify-full`, and any weaker value becomes `require`. `PGSSLROOTCERT` is respected. With `PGSERVICE` set, set `PGSSLMODE` to one of those three as well: a weaker or missing one exits 3, since the service file's `sslmode` cannot be checked |
| `--extension NAME` | none | Create an extension in schema `public`; repeatable. Trusted extensions work with any admin; untrusted ones need a superuser or a member of `rds_superuser`, `azure_pg_admin`, or `cloudsqlsuperuser` |
| `--sink NAME` | `file` | `file` or `terminal`; repeatable. `terminal` works only with an interactive terminal |
| `--sink-path PATH` | see below | Write the credentials file here instead; repeatable. Inside a git work tree, the path must be ignored |
| `--digits N` | `4` | Digits appended to each password (at least 4) |
| `--reader-read-only` / `--no-reader-read-only` | on | Default the reader's transactions to read-only. A mistake guard: the grants are the boundary |
| `--reader-idle-timeout` | `60s` | Reader's `idle_in_transaction_session_timeout`; `0` leaves it unset |
| `--reader-statement-timeout` | `5min` | Reader's `statement_timeout`; `0` leaves it unset |
| `--yes` / `-y` | off | Skip the confirmation prompt |

`create` refuses if the database or any of the four roles already exists. It
never adopts them. Recovery is `teardown`, then `create`.

### Credentials file

By default the passwords go to
`$XDG_DATA_HOME/ess-postgres-provision/<host>/<base>.env`, or under
`~/.local/share` when `XDG_DATA_HOME` is unset. The directory is `0700` and
the file `0600`. It is created exclusively, so an existing file is never
overwritten. Each role gets two lines:

```bash
BILLING_APP_DATABASE_PASSWORD=<password>
BILLING_APP_DATABASE_URL=postgresql://billing_app:<password>@db.example.com:5432/billing?sslmode=require
```

There is no single `DATABASE_URL`. Point migrations at the migrations URL and
the app at the app URL; mixing them up hands the app the power to drop
tables.

If a sink fails, the passwords go to a new `<base>.failed-<timestamp>.env`
in the same data directory.

If the run itself fails after the roles may exist, the passwords go to a
`failed` file instead of the usual one: beside each `--sink-path`, as
`<name>.failed-<timestamp><suffix>`, or without one, in the data directory.
Other `--sink` destinations still receive them, labelled as a failed run.

### `ess-postgres-provision verify BASE_NAME`

Read-only. Checks the catalog against the design: role attributes and
memberships, provenance markers, ownership, `CONNECT`, schema privileges,
`search_path`, default privileges, and extensions. Rerun it after
migrations: it also fails if the reader can write any table, the app can
truncate one, or `PUBLIC` can execute a function in the schema, and it lists
any `SECURITY DEFINER` function the reader can execute.

Takes `--host`, `--port`, `--admin-user`, `--allow-insecure`, `--extension`,
and `--no-reader-read-only` (for a database created with that flag).

### `ess-postgres-provision rotate BASE_NAME`

Sets new passwords for `--role owner|migrations|app|reader` (repeatable;
default all four) and writes them to a new
`<base>.rotated-<timestamp>.env`. The earlier file's lines for those roles
are then stale. Takes the connection, sink, `--digits`, and `--yes` flags.

### `ess-postgres-provision teardown BASE_NAME`

Drops the database and roles that `create` made, from whatever state a run
left. It refuses if a role lacks this tool's marker, the database has
another owner, or the database holds any data: dropping a database with
data stays a manual step. An extension's own tables are not data, but a row
in one of its configuration tables that `pg_dump` would dump is, and so is
a configuration table the admin cannot read. It blocks new connections
first, and refuses if other sessions are still connected unless
`--terminate-sessions` is passed, which needs superuser or
`pg_signal_backend`. If it fails partway, it leaves the database accepting
connections.

### Exit codes

| Exit | Meaning | Recovery |
| --- | --- | --- |
| 0 | Done and verified | None |
| 1 | Failed after roles may exist, or `verify` failed. Credentials are still delivered, labelled as a failed run | `teardown`, then `create` |
| 2 | Usage error | Fix the arguments |
| 3 | A check refused; nothing was written | Read the named check |
| 4 | No sink received the credentials, fallback included | `rotate` |
| 130, 143 | Interrupted after roles may exist; credentials delivered | As for 1 |

### Things to know

- **The reader can read every table**, including password hashes and session
  data if the schema holds them. Before handing the reader credential out,
  grant it reporting views instead, or do not issue it.
- **Functions migrations creates are not executable by `PUBLIC`**, so the
  reader cannot write through a `SECURITY DEFINER` function. If the reader
  needs a read-only function, grant it in the migration that creates it:
  `GRANT EXECUTE ON FUNCTION billing.report_totals() TO billing_reader;`.
- **Django's `createsuperuser`** creates a row in `auth_user` over the app
  connection. It is not a Postgres role and is unrelated to these four.
- **A pooler or BI tool that overrides `search_path`** must include
  `billing`.
- **The roles can still connect to other databases** that grant `PUBLIC`
  `CONNECT`, such as `postgres`. Closing that is a cluster-wide decision.

## Running tests

From a checkout of the repo that hosts this skill, with its uv workspace
synced:

```bash
uv run pytest skills/ess/ess-postgres-provision/scripts
```

Run this suite in its own command. This project installs a built copy of
`ess_passwords` without its tests, so in one command with the
`ess-passwords` tests, pytest's default import mode can fail to find them.
To run both suites together, add `--import-mode=importlib`.

Unit tests need no server. Integration tests run the CLI against a real
server and skip unless `ESS_POSTGRES_PROVISION_TEST_DSN` names a superuser
connection, for example:

```bash
ESS_POSTGRES_PROVISION_TEST_DSN="host=localhost dbname=postgres user=postgres" \
  uv run pytest skills/ess/ess-postgres-provision/scripts
```

To test against PostgreSQL 16 next to another local server, see
[Test against PostgreSQL 16 with Homebrew](test-postgresql-16-with-homebrew.md).

## License

Apache-2.0. See [LICENSE](../LICENSE). Passwords come from the
`ess-passwords` skill; the database driver is
[psycopg](https://www.psycopg.org/) (LGPL-3.0).
