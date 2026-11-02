---
description: Name shell scripts in kebab-case after what they do, and keep each self-test beside its script as test_<snake_case>.sh
applyTo: "**/*.sh"
---

# Shell File Naming

Shell has no standard file layout, so follow one convention everywhere.

| File | Case | Example |
| ---- | ---- | ------- |
| Script a person or tool runs | kebab-case, verb first | `find-review-requests.sh`, `safe-push.sh` |
| Its self-test | `test_` + the script name in snake_case | `test_find_review_requests.sh` |

- **Kebab-case for scripts.** A script is a command, and commands read as kebab-case
  (`git-subtree`, `apt-get`). Do not add snake_case scripts beside kebab-case ones.
- **Descriptive names, not `run.sh` or `main.sh`.** `$0`, error messages, `ps`, and
  editor tabs show only the file name, so it must say what the script does.
- **`test_` snake_case for tests.** Tests are never typed as commands, and the prefix
  matches pytest's `test_*.py`, so one search finds every test in the repo.

## Co-locate the test with its script

When a script has a test, give the pair its own directory, named after the script:

```text
scripts/
├── npx-skills-add/
│   ├── npx-skills-add.sh
│   └── test_npx_skills_add.sh
└── apm-lock-check-ignored/
    ├── apm-lock-check-ignored.sh
    └── test_apm_lock_check_ignored.sh
```

Several scripts that work together and share one directory, such as a skill's
`scripts/`, keep each test next to its script in that directory instead.

The test finds its script relative to itself, never through the working directory:

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/find-review-requests.sh" --repo acme/widgets
```

## Renaming

Rename with `git mv` and rename the test to match. Then search for the old name
(`rg -n 'old-name\.sh'`) and update every caller, doc, usage comment, and Makefile
or hook entry. When rewriting references in bulk, match whole file names, for example
`(?<![\w-])old_name\.sh`, so the script's new name is not spliced into
`test_old_name.sh`.
