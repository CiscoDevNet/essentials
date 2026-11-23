---
description: Configure and run pytest for a skill's scripts/ uv project so test runs leave nothing in the skill and a shared sibling package's tests collect regardless of order.
applyTo: "skills/**/scripts/**"
---

# Testing a skill's `scripts/` project

A skill can carry its CLI as a uv project in `scripts/`. Code shared between
skills lives in one skill's `scripts/` and is a non-editable path dependency
of the others, so that running a CLI never writes into an installed sibling.
Two pytest defaults break this layout.

## Turn off the pytest cache

`uv run pytest skills/<name>/scripts` makes that `scripts/` directory
pytest's root when no config file above it configures pytest, and pytest
writes `.pytest_cache` there. Skill installers such as APM copy every file in
the skill directory, git-ignored files included, so the cache reaches the
lock file and the deployed copy. In every `scripts/pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "-p no:cacheprovider"
```

## Run a shared package's tests apart from its consumers

A consumer's virtualenv holds a built copy of the shared package, which
excludes test files, and pytest collects the source tree. Python loads a
package once. Under pytest's default import mode, `prepend`, a test module is
imported by its package name, such as `shared_lib.test_main`. If a
consumer's tests imported `shared_lib` first, pytest looks for the test
module in the built copy and fails with `ModuleNotFoundError`. Order decides:
with the shared tests first, both suites pass.

This applies to every consumer in the same virtualenv, skill or not.

- Run each `scripts/` suite in its own pytest command, and document it that
  way in the skill's references.
- To run a shared package's tests together with a consumer's, pass
  `--import-mode=importlib` on the command line.
- Do not put `--import-mode=importlib` in `scripts/pyproject.toml`. Given
  several paths, pytest picks its root from their common ancestor and loads
  a config file above both skills, usually the repo root's, so the skill's
  setting never reaches a combined run.
- Do not set it repo-wide without first collecting the whole repo in both
  modes (`pytest --co -q --import-mode=<mode>`) and comparing the counts.
  Other suites can depend on the default mode.
- Keep the shared package non-editable and its tests out of its build.
  Making it editable to fix collection writes `__pycache__` into the
  installed sibling skill.
