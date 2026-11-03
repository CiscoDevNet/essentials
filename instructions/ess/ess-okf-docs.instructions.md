---
description: >-
  When editing or creating markdown with OKF YAML frontmatter (type, generated,
  tags, etc.), consult Context7 for the OKF v0.2 spec before guessing.
applyTo: "**/*.md"
---

Use the Context7 MCP for the Open Knowledge Format spec. Context7 is a
configured docs server in this repo. Do not call an `okf-spec` server; none
is defined.

1. Call `resolve-library-id` with library name `Open Knowledge Format` unless
   you already have the id `/googlecloudplatform/open-knowledge-format`
   (OKF v0.2, GoogleCloudPlatform/open-knowledge-format).
2. Call `query-docs` with that library id. Keep each query to one frontmatter
   concept (`type`, `title`, `description`, `tags`, `generated`).

`type` is the only required key. Consumers must tolerate unknown types and
preserve unknown keys.
