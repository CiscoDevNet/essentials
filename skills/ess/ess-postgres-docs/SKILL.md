---
name: ess-postgres-docs
description: >-
  Answer PostgreSQL and psql questions from current documentation through the
  Context7 MCP instead of training data. Use when the user asks about SQL
  syntax, the psql CLI, PostgreSQL administration, or configuration settings.
compatibility: Requires the Context7 MCP server.
---

When answering PostgreSQL questions (SQL syntax, psql CLI, administration, or
configuration), use the Context7 MCP. Do not rely on training data for
PostgreSQL command or API details.

1. Call `resolve-library-id` with library name `PostgreSQL` unless you already
   have the id `/websites/postgresql_current`.
2. Call `query-docs` with that library id. Prefer `/websites/postgresql_current`
   unless the user specifies a version. Keep each query to one command or
   setting.
