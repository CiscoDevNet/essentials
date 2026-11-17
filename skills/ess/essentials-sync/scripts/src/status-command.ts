import { createHash } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";
import { parseArgs } from "node:util";
import { JARGON_FILE_OPTION, parseJargonFileName, rethrowAsUsageError, UsageError } from "./args.ts";
import { findEssItemRoot, repoOwnedItemFiles } from "./ess-items.ts";
import { listPublishableFiles } from "./file-set.ts";
import { DEFAULT_JARGON_FILE } from "./jargon-list.ts";
import { PROGRAM_NAME } from "./program.ts";
import { assertDifferentRepos, resolveTargetRepo } from "./repos.ts";
import { style } from "./style.ts";

export type ItemState = "identical" | "differs" | "only in source" | "only in target";
export type FileState = "changed" | "only in source" | "only in target";

export interface ItemStatus {
  item: string;
  state: ItemState;
  files: Array<{ path: string; state: FileState }>;
}

export const STATUS_HELP = `Usage: ${PROGRAM_NAME} status --source-repo <path> [--target-repo <path>]

Report whether each ess-* item is identical in two repos. Compares the
publishable files (git ls-files, not ignored) by content and executable bit,
skipping each item's LICENSE and jargon file. Read-only: never prompts, needs
no API key.

Options:
  --source-repo <path>  Root of the repo the items come from
  --target-repo <path>  Root of the repo they sync into (default: the git root
                        of the current directory)
  --jargon-file <name>  Name of the jargon file to skip (default: ${DEFAULT_JARGON_FILE})
  -h, --help            Show this help`;

// `status`: compares every ess-* item in two repos, file by file. Read-only,
// so it never prompts and has no --dry-run. Returns the process exit code.
export async function runStatusCommand(argv: string[], cwd = process.cwd()): Promise<number> {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      options: {
        "source-repo": { type: "string" },
        "target-repo": { type: "string" },
        "jargon-file": JARGON_FILE_OPTION,
        help: { type: "boolean", short: "h" },
      },
    });
  } catch (error) {
    rethrowAsUsageError(error);
  }
  const { values } = parsed;
  if (values.help) {
    console.log(STATUS_HELP);
    return 0;
  }
  const sourceRepo = values["source-repo"];
  if (!sourceRepo) throw new UsageError("status needs --source-repo.");
  const jargonFile = parseJargonFileName(values["jargon-file"]);
  const sourceRepoAbs = path.resolve(cwd, sourceRepo);
  const targetRepoAbs = await resolveTargetRepo(values["target-repo"], cwd);
  await assertDifferentRepos(sourceRepoAbs, targetRepoAbs);

  const statuses = await compareEssItems(sourceRepoAbs, targetRepoAbs, repoOwnedItemFiles(jargonFile));
  for (const status of statuses) {
    console.log(formatItemStatus(status));
  }
  const identical = statuses.filter((status) => status.state === "identical").length;
  console.log(style.dim(`${identical} of ${statuses.length} item(s) identical.`));
  return 0;
}

export async function compareEssItems(
  sourceRepo: string,
  targetRepo: string,
  repoOwnedFiles: ReadonlySet<string> = repoOwnedItemFiles(),
): Promise<ItemStatus[]> {
  const [source, target] = await Promise.all([
    indexEssItems(sourceRepo, repoOwnedFiles),
    indexEssItems(targetRepo, repoOwnedFiles),
  ]);
  const items = [...new Set([...source.keys(), ...target.keys()])].sort();
  return items.map((item) => compareItem(item, source.get(item), target.get(item)));
}

function compareItem(
  item: string,
  source: Map<string, string> | undefined,
  target: Map<string, string> | undefined,
): ItemStatus {
  if (!target) return { item, state: "only in source", files: [] };
  if (!source) return { item, state: "only in target", files: [] };

  const files: ItemStatus["files"] = [];
  for (const file of [...new Set([...source.keys(), ...target.keys()])].sort()) {
    const sourceHash = source.get(file);
    const targetHash = target.get(file);
    if (sourceHash === undefined) files.push({ path: file, state: "only in target" });
    else if (targetHash === undefined) files.push({ path: file, state: "only in source" });
    else if (sourceHash !== targetHash) files.push({ path: file, state: "changed" });
  }
  return { item, state: files.length === 0 ? "identical" : "differs", files };
}

// Maps each ess-* item in the repo to its files (relative to the item; "" for
// an item that is a single file) and a fingerprint of each file.
async function indexEssItems(
  repoRoot: string,
  repoOwnedFiles: ReadonlySet<string>,
): Promise<Map<string, Map<string, string>>> {
  const items = new Map<string, Map<string, string>>();
  for (const relPath of await listPublishableFiles(repoRoot)) {
    const item = findEssItemRoot(relPath);
    if (!item) continue;
    const inner = relPath === item ? "" : relPath.slice(item.length + 1);
    if (repoOwnedFiles.has(inner)) continue;

    let files = items.get(item);
    if (!files) {
      files = new Map();
      items.set(item, files);
    }
    files.set(inner, await fingerprint(path.join(repoRoot, relPath)));
  }
  return items;
}

async function fingerprint(filePath: string): Promise<string> {
  const stat = await fs.lstat(filePath);
  if (stat.isSymbolicLink()) return `symlink:${await fs.readlink(filePath)}`;
  const digest = createHash("sha256").update(await fs.readFile(filePath)).digest("hex");
  return (stat.mode & 0o111) !== 0 ? `${digest}:x` : digest;
}

export function formatItemStatus(status: ItemStatus): string {
  const color = status.state === "identical" ? style.green : style.yellow;
  const lines = [`${color(status.state.padEnd(15))} ${status.item}`];
  for (const file of status.files) {
    lines.push(`  ${file.state.padEnd(15)} ${file.path || path.basename(status.item)}`);
  }
  return lines.join("\n");
}
