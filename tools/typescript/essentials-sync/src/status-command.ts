import { createHash } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";
import { Command } from "commander";
import chalk from "chalk";
import { findEssItemRoot } from "./ess-items.js";
import { listPublishableFiles } from "./file-set.js";

export type ItemState = "identical" | "differs" | "only in source" | "only in target";
export type FileState = "changed" | "only in source" | "only in target";

export interface ItemStatus {
  item: string;
  state: ItemState;
  files: Array<{ path: string; state: FileState }>;
}

// Each item's own LICENSE is allowed to differ: the open-source copy carries
// the license text, the source repo may not.
const IGNORED_ITEM_FILES = new Set(["LICENSE"]);

// `essentials-sync status`: compares every ess-* item in two repos, file by
// file. Read-only, so it never prompts and has no --dry-run. Returns the
// process exit code.
export async function runStatusCommand(argv: string[]): Promise<number> {
  const program = new Command("essentials-sync status")
    .description(
      "Report whether each ess-* item is identical in two repos. Compares the"
        + " publishable files (git ls-files, not ignored) by content and executable bit,"
        + " skipping each item's LICENSE.",
    )
    .requiredOption("--source-repo <path>", "Root of the first repo")
    .requiredOption("--target-repo <path>", "Root of the second repo")
    .parse(argv, { from: "user" });
  const opts = program.opts<{ sourceRepo: string; targetRepo: string }>();

  const statuses = await compareEssItems(path.resolve(opts.sourceRepo), path.resolve(opts.targetRepo));
  for (const status of statuses) {
    console.log(formatItemStatus(status));
  }
  const identical = statuses.filter((status) => status.state === "identical").length;
  console.log(chalk.dim(`${identical} of ${statuses.length} item(s) identical.`));
  return 0;
}

export async function compareEssItems(sourceRepo: string, targetRepo: string): Promise<ItemStatus[]> {
  const [source, target] = await Promise.all([indexEssItems(sourceRepo), indexEssItems(targetRepo)]);
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
async function indexEssItems(repoRoot: string): Promise<Map<string, Map<string, string>>> {
  const items = new Map<string, Map<string, string>>();
  for (const relPath of await listPublishableFiles(repoRoot)) {
    const item = findEssItemRoot(relPath);
    if (!item) continue;
    const inner = relPath === item ? "" : relPath.slice(item.length + 1);
    if (IGNORED_ITEM_FILES.has(inner)) continue;

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
  const color = status.state === "identical" ? chalk.green : chalk.yellow;
  const lines = [`${color(status.state.padEnd(15))} ${status.item}`];
  for (const file of status.files) {
    lines.push(`  ${file.state.padEnd(15)} ${file.path || path.basename(status.item)}`);
  }
  return lines.join("\n");
}
