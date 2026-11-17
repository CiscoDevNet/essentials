# CLI reference

```bash
node "$SKILL_DIR/scripts/src/cli.ts" <command> [options]
```

Every command takes `--help`.

| Command | Writes | Needs `CURSOR_API_KEY` | What it does |
| --- | --- | --- | --- |
| `preflight` | no | no (it checks for one) | Checks Node 24+, git, npm, `CURSOR_API_KEY`, the SDK cache, and trufflehog. Exits 1 on any `FAIL`. |
| `sync` | yes | yes | Extracts a generic package from a tool, then syncs it into the target repo. |
| `scan <path>...` | no | no | Runs the deterministic scanners. Exits 1 on any critical finding. |
| `status` | no | no | Compares every `ess-*` item in two repos. Always exits 0. |
| `models` | no | yes | Prints the model IDs available to the key. |

## sync

```
sync --source <path> --target-repo <path> [options]
```

| Option | Required | Description |
| --- | --- | --- |
| `-s`, `--source <path>` | yes | The item to sync. In extract mode (the default) a `tools/python/<name>/` directory inside the source repo. With `--no-extract`, a directory or a single file, such as `instructions/ess/ess-<name>.instructions.md`. |
| `-r`, `--target-repo <path>` | yes | Root of the target repo. Must be a git work tree. |
| `-t`, `--target-path <path>` | with `--no-extract` | Where the item lands, relative to `--target-repo`. Default in extract mode: `packages/python/<package-name>`. |
| `--source-repo <path>` | no | Source repo root. Default: the git root above `--source`. |
| `--package-name <name>` | no | Name of the extracted package. Must start with `ess-` and be kebab-case. Default: `ess-<basename of --source>`. |
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

`sync` prints the plan (paths, mode, models), then asks on stderr before writing.
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
end of a fast copy. Each item's `LICENSE` belongs to the repo that holds it: it is
never copied, and files that exist only in the target are left alone.

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
| 1 | Could not start: bad arguments, missing `CURSOR_API_KEY`, no `--yes` without a terminal, an aborted prompt, or an agent startup error. |
| 2 | A phase still has critical findings after `--max-revisions`. Both trees are left dirty. |
| 3 | The primary agent failed mid-run. The logged `agent` and `run` IDs identify it in the Cursor dashboard. |

## scan

```
scan [--no-trufflehog] [--no-secretlint] <path>...
```

A path inside an `ess-*` item scans the whole item; any other path is scanned as
given. Jargon findings are critical. Each finding prints as file, line, scanner,
and rule; secret findings never print the matched value.

## status

```
status --source-repo <path> --target-repo <path>
```

Lists every `ess-*` item in either repo as `identical`, `differs` (with the files
that changed or exist on one side only), `only in source`, or `only in target`. An
item is a directory named `ess-*`, or a file named `ess-*` inside a directory named
`ess` (`instructions/ess/`). Files are compared by content and executable bit, from
the same file list the copy uses. Each item's `LICENSE` is skipped, and
dot-directories (`.agents/`, `.cursor/`) are ignored as installed copies.

## Jargon wordlist

The jargon scanner matches a built-in list of company terms, plus extra terms from a
`.essentials-sync-jargon.json` beside the source item (`scan` also reads one at the
repo root). The file is a flat array, or an object:

```json
{
  "terms": ["internal-codename", "*.internal.example.com"]
}
```

Entries that start with `*.` match hostnames with that suffix; everything else is a
case-insensitive whole-word match. Put per-organization employee-ID patterns here
too: the PII scanner only flags emails, phone numbers, and SSNs.
