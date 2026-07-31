# essentials-sync

Extract a jargon-free `ess-*` shared package out of a team- or account-specific tool in your private repo, then sync it to the open-source `essentials` repo. Single command. Deterministic scanners and an adversarial LLM reviewer between you and either tree.

## Example

```bash
essentials-sync \
  --source ~/code/<private-repo>/tools/python/foo-client \
  --target-repo ~/code/essentials
```

That invocation produces three artifacts across two repos:

```
<private-repo>/tools/python/foo-client/           (rewritten as a thin wrapper, company defaults)
<private-repo>/packages/python/ess-foo-client/    (NEW: generic core, no defaults)
essentials/packages/python/ess-foo-client/        (NEW: copy of the generic core)
```

The wrapper depends on the extracted package via `[tool.uv.sources] ess-foo-client = { workspace = true }`. The extracted and synced packages are scanned and reviewed; the wrapper is intentionally left alone so it can keep the company-specific defaults that justify its existence.

## How it works

Two phases run sequentially in a single invocation:

**Phase A (extract, writes to the source repo).** A primary model (highest available Opus by default) reads the original tool, splits the reusable logic into `packages/python/ess-<name>/`, and rewrites `tools/python/<name>/` as a wrapper that imports the new package and supplies the company defaults. The extracted package is then scanned by TruffleHog, secretlint, the jargon regex, and the PII regex. If any critical findings remain, the agent is asked to revise -- up to `--max-revisions` iterations.

**Phase B (sync, writes to the target repo).** Once Phase A is clean, a fresh primary agent copies the extracted package into `essentials/packages/python/ess-<name>/`. The result is scanned again, then an adversarial reviewer running on a different model family (highest available Codex by default) does a paranoid pass. Findings flow back into the scan-and-revise loop.

Critical findings block; non-blocking reviewer findings are surfaced as warnings so you can address them by hand. On success, both working trees are left dirty for you to review with `git diff` and commit yourself.

For sources that are already generic and don't need an extract step, pass `--no-extract` and the tool runs Phase B only against `--source`.

### Fast-path copy

When `--no-extract` is set and the source pre-scan comes back with **zero** findings, Phase B skips the primary agent and copies the tree verbatim instead. The copy is still held to the same bar afterwards: deterministic scanners run against the target, then the adversarial reviewer. If either surfaces a critical finding, the run escalates to the primary agent and continues as normal.

This exists because a clean source gives the primary agent nothing useful to do, and an agent asked to generalize an already-generic tree will paraphrase working prose and drop valid cross-references instead. On a 16-file skill directory the fast path finished in 27s with zero content drift, against 11min and 187 rewritten lines for the agent path.

The copy honors `.gitignore` and skips the same cache and build directories the scanners skip. That is a safety property, not an optimization: the scanners never read gitignored paths, so copying them would ship content nothing vouched for (`.env`, local credentials). Anything copied that the text scanners could not read -- binaries, files over the 5 MB cap -- is listed explicitly at the end of the run. Files that exist only in the target (`LICENSE`, `NOTICE`) are left untouched, so re-syncing never clobbers them.

Pass `--no-fast-copy` to force the agent path regardless.

## Installation

```bash
cd essentials/tools/typescript/essentials-sync
nvm use                               # picks up local .nvmrc (Node 22.19.0)
pyenv shell                           # picks up local .python-version (3.11.11)
npm install
npm run build
npm link                              # optional: puts `essentials-sync` on $PATH
brew install trufflehog
```

This package pins its own Node and Python versions (`.nvmrc` + `.python-version`) that diverge from the parent `essentials/` repo. The reason: `@cursor/sdk` pulls in a `sqlite3` build that requires `distutils` (removed in Python 3.12) when it can't find a prebuilt binary. See "Install troubleshooting" below for the full story.

Required environment variable:

```bash
export CURSOR_API_KEY=cursor_...      # cursor.com/dashboard/integrations -> API Keys
```

Or copy `.env.example` to `.env` and edit it; the CLI auto-loads `.env` from the current working directory and from the package root (`essentials-sync/.env`). Pre-existing process env vars take precedence over `.env` values.

Optional environment variables:

- `CURSOR_MODEL` -- default primary model spec (overrides the `opus` sentinel).
- `CURSOR_REVIEW_MODEL` -- default reviewer model spec (overrides the `codex` sentinel).

### Install troubleshooting

The local `.nvmrc` (Node 22.19.0) and `.python-version` (3.11.11) handle this for anyone using `nvm` + `pyenv`. If you don't use those:

`@cursor/sdk` transitively depends on `sqlite3@5.1.7`, which can fall back to compiling a native addon at install time. That fallback path bundles `node-gyp@8`, which still imports `distutils` -- removed in Python 3.12 per [PEP 632](https://peps.python.org/pep-0632/). If `npm install` dies with `ModuleNotFoundError: No module named 'distutils'`, point npm at a Python that still has it (3.11 or earlier):

```bash
# one-time, for this install
npm_config_python=/path/to/python3.11 npm install

# or persist via .npmrc using env-var substitution (npm 8.6+)
echo 'python = ${HOME}/.pyenv/versions/3.11.11/bin/python3' >> .npmrc
```

Why a per-package pin: the parent `essentials/` repo pins Python 3.12 globally, which is what the rest of the workspace needs. This package overrides the Python pin only inside its own directory; `pyenv` honors the deepest `.python-version` walking up the tree.

## Customizing the jargon wordlist

Drop a `.essentials-sync-jargon.json` file at the root of the original source tool (or, in `--no-extract` mode, the source package) to extend the built-in wordlist. Either a flat array or `{ "terms": [...] }` is accepted:

```json
{
  "terms": [
    "internal-codename",
    "*.internal.example.com"
  ]
}
```

Entries that start with `*.` are treated as hostname suffixes; everything else as case-insensitive word-boundary matches. Per-org employee-ID patterns belong here too -- the bundled PII scanner only flags emails, phone numbers, and SSNs.

## Usage

```
essentials-sync [options]
```

| Option | Required | Description |
| --- | --- | --- |
| `--source <path>` | yes | Absolute path to the source tool directory. In default (extract) mode this must be a `tools/python/<name>/` directory inside the source repo. |
| `--target-repo <path>` | yes | Absolute path to the target repo root. Must be a git working tree. |
| `--target-path <path>` | no | Path relative to `--target-repo` where the synced package lands. Default: `packages/python/<package-name>`. Required when `--no-extract` is set. |
| `--source-repo <path>` | no | Source repo root. Default: the git root discovered by walking up from `--source`. |
| `--package-name <name>` | no | Override for the extracted `ess-*` package name. Must start with `ess-` and be kebab-case. Default: `ess-<basename of --source>`. |
| `--no-extract` | no | Skip Phase A. Assume `--source` is already a generic package and only run the sync to essentials. |
| `--no-fast-copy` | no | Always let the primary agent author the sync, even when the source scan is completely clean. See [Fast-path copy](#fast-path-copy). |
| `--model <spec>` | no | Primary model. Accepts a concrete ID, a family sentinel (`opus`, `codex`, `claude`, `gpt`, `gemini`, `composer`), or `auto`. Default: `opus`. |
| `--review-model <spec>` | no | Adversarial reviewer model. Same shape as `--model`. Default: `codex`. |
| `--max-revisions <n>` | no | Maximum scan-and-revise iterations *per phase*. Default: `3`. |
| `--dry-run` | no | Write to a temp directory instead of `--target-path`. |
| `--no-source-scan` | no | Skip the informational source pre-scan. |
| `--no-adversarial-review` | no | Skip the LLM reviewer; run deterministic scanners only. |
| `--list-models` | no | Print the available model IDs for your `CURSOR_API_KEY` and exit. |

The `opus` sentinel resolves to the highest-version Opus model on your Cursor account; `codex` to the highest-version Codex; etc. Fallback chains kick in if a family is unavailable (primary: `opus` -> any `claude` -> `auto`; reviewer: `codex` -> any `gpt` -> any non-primary -> `auto`). The resolver prefers the canonical version of each family (e.g. `gpt-5.3-codex` over `gpt-5.3-codex-spark`) and always logs the pair it chose so you can see what actually ran.

### Scan coverage

In extract mode (the default), scanners only run against the **extracted package**, not the wrapper. That is deliberate: the wrapper exists to hold the company-specific defaults that the open-source library cannot ship with. In `--no-extract` mode, scanners run against the sync target (the essentials copy) as before.

Files whose basename starts with `tmp-` or `tmp.` are skipped by the deterministic scanners and the adversarial reviewer. Use this for working notes the agent leaves for you (the `tmp-RECOMMENDATIONS.md` it writes when the source has heavy jargon, for example) -- target repos are expected to gitignore the `tmp[-.]*` pattern so these files never get committed.

## Exit codes

- `0` -- both phases clean; review and commit yourself.
- `1` -- could not start (bad args, missing API key, agent startup error).
- `2` -- a phase still has critical findings after `--max-revisions`. Both working trees are left dirty for inspection.
- `3` -- primary agent ran but failed mid-execution. Use the logged `agent` and `run` IDs to investigate via `Agent.getRun(...)` or the Cursor dashboard.

## Running tests

```bash
npm test
```

Tests use [Vitest](https://vitest.dev) and cover the jargon and PII scanners against the `clean-package` and `dirty-package` fixtures under `tests/fixtures/`, the extract-plan name/path derivation logic, the verbatim copy (including that it refuses to copy gitignored files and preserves executable bits), and the fast-path eligibility gate.

## License

[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/).
