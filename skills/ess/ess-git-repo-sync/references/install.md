# Installation

The skill ships source only. Nothing is ever installed inside the skill directory:
skill installers copy it verbatim, generated files included.

| Piece | Where it comes from | When |
| --- | --- | --- |
| The CLI | `node` runs `scripts/src/*.ts` directly (type stripping) | always; needs Node 24+ |
| secretlint | `npx`, pinned in `scripts/src/scanners/secretlint.ts`, cached in `~/.npm/_npx` | first scan |
| `@cursor/sdk` | `npm ci` from `scripts/sdk/`, into the user cache | first `sync` or `models` |
| trufflehog | your package manager (`brew install trufflehog`) | optional |

## The SDK cache

The first `sync` or `models` copies `scripts/sdk/package.json` and its lockfile to
`${XDG_CACHE_HOME:-~/.cache}/ess-git-repo-sync/sdk-<hash>/` and runs
`npm ci --omit=dev` there. The hash covers both files, so a version bump installs
fresh beside the old one. The install happens in a temp directory that is renamed
into place, so an interrupted install never looks complete. `preflight` prints the
directory.

To reinstall, delete the directory and run `models`. To free space, delete
`${XDG_CACHE_HOME:-~/.cache}/ess-git-repo-sync/`.

## Install failures

### sqlite3 and distutils

`@cursor/sdk` depends on `sqlite3`, whose install script downloads a prebuilt
binary and, when none matches, compiles one with a bundled `node-gyp` that still
imports `distutils`, removed in Python 3.12
([PEP 632](https://peps.python.org/pep-0632/)). If `npm ci` fails with
`ModuleNotFoundError: No module named 'distutils'`, point npm at Python 3.11 or
earlier for one install:

```bash
npm_config_python=/path/to/python3.11 node "$SKILL_DIR/scripts/src/cli.ts" models
```

### Blocked install scripts

Newer npm releases (11.19, for one) skip dependency install scripts unless
`package.json` allows them. `scripts/sdk/package.json` allows `sqlite3` by exact version in
`allowScripts`; keep that entry in step with the lockfile when bumping the SDK.
