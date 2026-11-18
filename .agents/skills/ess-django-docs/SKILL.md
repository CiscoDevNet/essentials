---
name: ess-django-docs
description: >-
  Answer Django questions from current documentation through the Context7 MCP
  instead of training data. Use when the user asks about Django APIs, settings,
  the ORM, migrations, management commands, or Django REST Framework details.
license: Apache-2.0
compatibility: Requires the Context7 MCP server.
---

When answering Django questions, use the Context7 MCP. Do not rely on
training data for Django API details.

1. Call `resolve-library-id` with library name `Django` unless you already
   have a Django library id.
2. Call `query-docs` with that library id. Keep each query to one Django
   API or setting.
