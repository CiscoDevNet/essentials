# CLI reference

```bash
node "$SKILL_DIR/scripts/src/cli.ts" <command> [options]
```

Every command takes `--help`.

| Command | Writes | Needs `CURSOR_API_KEY` | What it does |
| --- | --- | --- | --- |
| `preflight` | no | no (it checks for one) | Checks Node 24+, git, npm, `CURSOR_API_KEY`, the SDK cache, and trufflehog, and reports the current repo and its jargon file. Exits 1 on any `FAIL`. |
| `sync` | yes | yes | Extracts a generic package from a tool, then syncs it into the target repo. |
| `scan <path>...` | no | no | Runs the deterministic scanners. Exits 1 on any critical finding. |
| `status` | no | no | Compares every `ess-*` item in two repos. Exits 0 unless the arguments are bad. |
| `models` | no | yes | Prints the model IDs available to the key. |

`preflight`, `sync`, `scan`, and `status` take `--jargon-file <name>`; see
[Jargon wordlist](#jargon-wordlist).

## sync

```
sync --source <path> [options]
```

| Option | Required | Description |
| --- | --- | --- |
| `-s`, `--source <path>` | yes | The item to sync. In extract mode (the default) a `tools/python/<name>/` directory inside the source repo. With `--no-extract`, a directory or a single file, such as `instructions/ess/ess-<name>.instructions.md`. |
| `-r`, `--target-repo <path>` | no | Root of the target repo. Default: the git root of the current directory. Must be a git work tree, and not the source repo. |
| `-t`, `--target-path <path>` | no | Where the item lands, relative to the target repo. Default: the item's path relative to the source repo (in extract mode, the extracted package's: `packages/python/<package-name>`). |
| `--source-repo <path>` | no | Source repo root. Default: the git root above `--source`. |
| `--package-name <name>` | no | Name of the extracted package. Must start with `ess-` and be kebab-case. Default: `ess-<basename of --source>`. |
| `--jargon-file <name>` | no | Name of the jargon file. Default: `jargon.json`. |
| `-m`, `--model <spec>` | no | Primary model: a concrete ID, a family (`opus`, `codex`, `claude`, `gpt`, `gemini`, `composer`), or `auto`. Default: `opus`, or `CURSOR_MODEL`. |
| `--review-model <spec>` | no | Adversarial reviewer model, same forms. Default: `codex`, or `CURSOR_REVIEW_MODEL`. |
| `--max-revisions <n>` | no | Scan-and-revise iterations per phase. Default: `3`. |
| `--dry-run` | no | Run everything against staging repos in the temp directory. Wins over `--yes`. |
| `-y`, `--yes` | no | Skip the confirmation prompt. Required when there is no terminal. |
| `--no-extract` | no | Skip Phase A; `--source` is already generic. |
| `--no-fast-copy` | no | Always let the primary agent author the sync. |
| `--no-source-scan` | no | Skip the informational scan of the source. |
| `--no-adversarial-review` | no | Deterministic scanners only. |

### Phases

Extract mode requires a uv workspace in the source repo: a root `pyproject.toml`
with `[tool.uv.workspace]`, the tool in `tools/python/<name>/`, and the package
written to `packages/python/ess-<name>/`. With `--no-extract`, the source can be
laid out any way.

**Phase A, extract (writes to the source repo).** The primary model reads the tool,
moves its reusable logic into `packages/python/ess-<name>/`, and rewrites
`tools/python/<name>/` as a thin wrapper that imports the new package and supplies
the company defaults. The wrapper depends on the package through
`[tool.uv.sources] ess-<name> = { workspace = true }`. The extracted package is then
scanned, and the agent revises until no critical finding remains or
`--max-revisions` runs out. The wrapper is never scanned: it exists to hold the
company-specific defaults.

**Phase B, sync (writes to the target repo).** A fresh primary agent copies the
package (or, with `--no-extract`, the source item) into the target. The result is
scanned, then the adversarial reviewer, on a different model family, does a
paranoid pass. Its critical findings go back into the same revise loop;
non-blocking ones are printed as warnings to handle by hand.

On success, both working trees are left dirty for the user to review and commit.

### Confirmation and dry run

`sync` prints the plan (the source and target repos, paths, mode, the jargon files
read, and the models), then asks on stderr before writing.
`--yes` skips the question. Without a terminal, a real sync fails fast unless
`--yes` is passed.

`--dry-run` needs no confirmation. It stages a fresh git repo as the target, seeded
with the item's current contents there. In extract mode it also stages the source:
a git repo holding only the root `pyproject.toml`, the tool, and any existing
extracted package. The run then proceeds exactly as a real one, against the staging
repos, whose paths it prints.

### Fast-path copy

With `--no-extract`, when the source scan finds **nothing at all**, Phase B skips the
primary agent and copies the tree verbatim. The copy is still scanned and reviewed;
a critical finding hands the run to the primary agent.

A clean source gives the agent nothing to do, and an agent asked to generalize an
already-generic tree paraphrases working prose and drops valid cross-references.

### The file list

The copy and the scanners read one list: `git ls-files --cached --others
--exclude-standard`, so every ignore rule git applies counts, including
`.gitignore` files above the item. Paths must be inside a git work tree. Cache and
build directories and `tmp-*` / `tmp.*` working notes are always skipped. The
scanners never read ignored paths, so copying them would ship content nothing
vouched for (`.env`, local credentials).

Files the text scanners cannot read (binaries, files over 5 MB) are listed at the
end of a fast copy. Each item's `LICENSE` and jargon file belong to the repo that
holds it: they are never copied, and files that exist only in the target are left
alone. The scanners skip the jargon file at the scanned root, since it lists the
very terms they look for.

### Models

The `opus` sentinel resolves to the highest-version Opus model on the account,
`codex` to the highest-version Codex, and so on, preferring each family's canonical
ID (`gpt-5.3-codex` over `gpt-5.3-codex-spark`). Fallbacks: primary `opus`, then any
`claude`, then `auto`; reviewer `codex`, then any `gpt`, then `auto`, never the
primary's model if another exists. The chosen pair is always printed.

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Both phases clean. |
| 1 | Could not start: bad arguments, the source and target are the same repo, no jargon terms, missing `CURSOR_API_KEY`, no `--yes` without a terminal, an aborted prompt, or an agent startup error. |
| 2 | A phase still has critical findings after `--max-revisions`. Both trees are left dirty. |
| 3 | The primary agent failed mid-run. The logged `agent` and `run` IDs identify it in the Cursor dashboard. |

## scan

```
scan [--jargon-file <name>] [--no-trufflehog] [--no-secretlint] <path>...
```

A path inside an `ess-*` item scans the whole item; any other path is scanned as
given. The jargon terms come from the jargon file at the git root and at each
scanned directory; with none, `scan` exits 1. Jargon findings are critical. Each
finding prints as file, line, scanner, and rule; secret findings never print the
matched value.

## status

```
status --source-repo <path> [--target-repo <path>] [--jargon-file <name>]
```

`--target-repo` defaults to the git root of the current directory, and must not be
the source repo.

Lists every `ess-*` item in either repo as `identical`, `differs` (with the files
that changed or exist on one side only), `only in source`, or `only in target`. An
item is a directory named `ess-*`, or a file named `ess-*` inside a directory named
`ess` (`instructions/ess/`). Files are compared by content and executable bit, from
the same file list the copy uses. Each item's `LICENSE` and jargon file are
skipped, and dot-directories (`.agents/`, `.cursor/`) are ignored as installed
copies.

## Jargon wordlist

The CLI has no built-in company terms. Each repo lists its own in a `jargon.json`
(or the name given with `--jargon-file`, a file name rather than a path). The file
is a flat array, or an object:

```json
{
  "terms": ["internal-codename", "*.internal.example.com"],
  "allow": {
    "paths": ["docs/history/**"],
    "text": ["status.internal.example.com"]
  }
}
```

Entries that start with `*.` match hostnames with that suffix; everything else is a
case-insensitive whole-word match that also finds the word inside identifiers: the
term `acme` matches `acme_auth`, `ACME_URL`, `AcmeClient`, and `getAcme`, but not
`Acmeville`. The words of a term match with any separator between them, or none:
`acme-internal` also matches `acme_internal`, `Acme Internal`, `ACME_INTERNAL`, and
`AcmeInternal`, so list each term once. To let one public spelling through, add it
to `allow.text`. Put per-organization employee-ID patterns here
too: the PII scanner only flags emails, phone numbers, and SSNs, and skips lock
files such as `package-lock.json` and `uv.lock`, whose registry metadata carries
upstream maintainers' addresses.

`allow.text` entries are literal strings, in exact case, blanked out of a line
before matching: list a public name that contains a term, such as an org name in
a repo URL, and a term elsewhere on the line is still caught. Every command
honors them, and `sync` lists them for the agent and the reviewer. `allow.paths`
is read only by the git hooks ([hooks.md](hooks.md)).

Where each command looks, merging the terms it finds:

| Command | Locations |
| --- | --- |
| `sync` | The source repo root, the source item (the original tool in extract mode), and the target repo root. |
| `scan` | The git root of the current directory, and each scanned directory. |
| `jargon-check.ts` (hooks) | The repo root. |

`sync` (dry runs included), `scan`, and the hooks fail closed: with no terms at any
location, they exit 1 and name the paths they checked. A file that is not valid
JSON is an error, not an empty list. The terms are also sent to Cursor in the agent
and reviewer prompts.

Keep the wordlist in the private source repo. The CLI never copies an item-level
jargon file, but a jargon file at the target repo root is published with that repo.
