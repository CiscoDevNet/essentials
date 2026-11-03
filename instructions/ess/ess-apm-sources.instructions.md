---
description: Author skills in skills/ and rules in instructions/, then deploy them with APM. Never add or edit files in .agents/skills/, .cursor/rules/, or any other agent rules/ directory by hand.
applyTo: "**/.agents/skills/**,**/.cursor/skills/**,**/.claude/skills/**,**/.cursor/rules/**,**/.claude/rules/**,**/.windsurf/rules/**"
---

# APM Sources

[APM](https://microsoft.github.io/apm/) deploys skills and rules into the directories each
agent reads. Those directories hold build output. Author in the source directory and let
APM write the copy.

| To add or change | Author it in | APM deploys it to |
| --- | --- | --- |
| A skill | `skills/<name>/SKILL.md` | `.agents/skills/<name>/` |
| A rule scoped to files | `instructions/<name>.instructions.md` | `.cursor/rules/<name>.mdc`, or the host's `rules/` directory |

Never create, edit, or delete files in `.agents/skills/`, `.cursor/skills/`,
`.cursor/rules/`, or any other agent's `rules/` directory by hand. `apm install` overwrites
hand edits, and a file APM does not track never reaches the other agents the repo targets.

## Add a skill or rule

1. Write the source under `skills/` or `instructions/`.
2. Declare it in `apm.yml`:

   ```yaml
   dependencies:
     apm:
       - path: ./skills/my-skill
       - path: ./instructions/my-rule.instructions.md
   ```

3. Run `apm install`, or the repo's wrapper for it.
4. Commit the source, `apm.yml`, `apm.lock.yaml`, and the deployed files together.

To change an existing skill or rule, edit the source and rerun step 3. If a deployed file
has no source, because `apm.lock.yaml` does not list it, move it into `skills/` or
`instructions/` before changing it.

A third-party skill is an APM dependency too. Declare its git source in `apm.yml` instead
of copying it into `.agents/skills/`.

## What does not fit an instruction

An instruction's frontmatter holds only `description` and `applyTo`, so APM cannot deploy
a rule that applies in every conversation. Put always-on guidance in `AGENTS.md`. Guidance
tied to a task rather than to files becomes a skill.
