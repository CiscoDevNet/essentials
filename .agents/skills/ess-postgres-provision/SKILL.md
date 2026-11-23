---
name: ess-postgres-provision
description: >-
  Provision a PostgreSQL database for an app: from one base name, create the
  database, a dedicated schema, and four separated login roles (owner,
  migrations, app, read-only reader) with generated passwords, verify the
  grants by logging in as each role, and write the credentials to a private
  file. Also verifies, rotates passwords for, and tears down what it created.
  Use when the user asks to set up, create, or provision a Postgres database
  or database users for Django or another web app, separate migration and app
  credentials, rotate those passwords, check the grants after migrations, or
  remove a database this skill created.
license: Apache-2.0
compatibility: >-
  Requires uv, network access to the PostgreSQL 16+ server, and an admin role
  that is a superuser or has CREATEDB and CREATEROLE (an RDS master
  qualifies). Install with APM so the ess-passwords skill lands beside it.
  The first run fetches click and psycopg from PyPI.
metadata:
  author: Matt Norris
  version: "0.1.0"
---

# Postgres provisioning

One command turns a base name such as `billing` into database and schema
`billing` and roles `billing_owner`, `billing_migrations`, `billing_app`, and
`billing_reader`. The migrations role creates tables, the app role reads and
writes rows, and the reader only reads. The CLI checks everything before it
writes, verifies the result as each role, and writes the passwords to a
`0600` file that you report but never open.

`SKILL_DIR` below is the absolute path of the directory containing this
`SKILL.md`. Do not use a repo-relative path; the skill may be installed
outside the repo.

## 1. Check the skills it composes

The CLI takes its password generator from the `ess-passwords` skill, which
APM installs beside this one. Check before the first run:

```bash
test -f "$SKILL_DIR/../ess-passwords/scripts/pyproject.toml" \
  && echo "ess-passwords present" \
  || echo "MISSING ess-passwords: stop and ask the user"
```

If it is missing, STOP. Tell the user to install this skill with
`apm install`, which brings its dependencies; `npx skills add` and manual
copies do not. Do not generate passwords another way.

| Skill | Use it for |
| --- | --- |
| [ess-passwords](../ess-passwords/SKILL.md) | Required: the CLI imports its generator |
| [ess-env-credentials](../ess-env-credentials/SKILL.md) | When the admin password is missing (step 2) |
| [ess-postgres-docs](../ess-postgres-docs/SKILL.md) | PostgreSQL questions the user asks along the way |
| [ess-django-docs](../ess-django-docs/SKILL.md) | Wiring the credentials into Django `DATABASES` |

## 2. Gather the inputs

Ask for anything the user has not given. Never infer a base name.

- **Base name**: 1 to 41 lowercase letters, digits, and underscores,
  starting with a letter.
- **`--host`** and **`--port`**: a hostname, or a Unix socket directory such
  as `/tmp` for a local server.
- **`--admin-user`**: the role that provisions.
- **Extensions**, opt-in by name with `--extension NAME`, for example
  `vector` or `pg_trgm`. Default none.

The admin password comes from `PGPASSWORD` or `~/.pgpass`, never a flag. You
run without a terminal, so the CLI cannot prompt. If it fails for a missing
password, follow `ess-env-credentials`: ask before sourcing the project's
`.env`, and never read or print it.

## 3. Dry-run, then STOP

Every write takes `--dry-run` before the subcommand. A dry run performs every
check and prints the SQL with password verifiers as `'***'`:

```bash
uvx --from "$SKILL_DIR/scripts" ess-postgres-provision --dry-run create billing \
  --host db.example.com --admin-user db_provisioner --yes
```

Show the user the header (`Connecting as`, `Target`, `Will create`,
`Credentials to`) and any refusal. STOP until the user confirms the target
and name. Then rerun without `--dry-run`. Keep `--yes`: without a terminal,
the CLI refuses to run a write without it.

## 4. Read the result

| Exit | Meaning | What to do |
| --- | --- | --- |
| 0 | Created and verified | Report the credentials file path and the verification table |
| 1 | Failed after roles may exist | Credentials still went to a `.failed-<timestamp>` file, named in the error. Report its path and the printed `teardown` command |
| 2 | Bad arguments | Fix them |
| 3 | A check refused; nothing was written | Quote the named check. A non-local host without SSL needs TLS, not `--allow-insecure`, unless the user says so |
| 4 | No sink received the credentials | Tell the user; the fix is `rotate` |
| 130, 143 | Interrupted after roles may exist | As for 1 |

The credentials file holds a `<BASE>_<ROLE>_DATABASE_PASSWORD` and a
`<BASE>_<ROLE>_DATABASE_URL` line per role. Tell the user to point migrations
at the migrations URL and the app at the app URL. There is deliberately no
single `DATABASE_URL`.

## Rules

- **Never open, read, `cat`, or `source` the credentials file**, and never put
  a password in chat, a commit, or a summary. Report the path only.
- **Never pass `--sink terminal`.** Keep the default file sink; the CLI
  refuses the terminal sink without a terminal anyway.
- **Never retry a refused `create` by deleting things.** `create` refuses if
  the database or any role exists. Recovery is `teardown`, then `create`.
- **`rotate` and `teardown` are writes**: dry-run, show the plan, STOP for
  confirmation, then run with `--yes`. `teardown` refuses a database that
  holds data; dropping one stays a manual step for the user.

## Tell the user

- **The reader can read every table**, including password hashes and session
  data. Say so before they hand the reader credential out.
- **Django's `createsuperuser`** creates an `auth_user` row over the app
  connection. It is not a Postgres role.
- **Rerun `verify` after migrations.** It then also checks that the reader
  cannot write any table and the app cannot truncate one:

  ```bash
  uvx --from "$SKILL_DIR/scripts" ess-postgres-provision verify billing \
    --host db.example.com --admin-user db_provisioner
  ```

Read [references/cli.md](references/cli.md) for every flag, the reader
guardrail options, `rotate --role`, and `teardown --terminate-sessions`. To
test the CLI itself against PostgreSQL 16 on macOS, read
[references/test-postgresql-16-with-homebrew.md](references/test-postgresql-16-with-homebrew.md).
