import { promises as fs } from "node:fs";
import path from "node:path";
import { parseArgs } from "node:util";
import { rethrowAsUsageError, UsageError } from "./args.ts";
import { runScanners } from "./scanners/index.ts";
import { findEssItemRoot, findGitRoot } from "./ess-items.ts";
import { loadJargonOverrides } from "./jargon-overrides.ts";
import { PROGRAM_NAME } from "./program.ts";
import { style } from "./style.ts";
import type { Finding } from "./types.ts";

export const SCAN_HELP = `Usage: ${PROGRAM_NAME} scan [options] <path>...

Scan files or directories with the deterministic scanners (secrets, jargon,
PII). A path inside an ess-* item scans the whole item. Exits 1 on critical
findings. Read-only: never prompts, needs no API key.

Options:
  --no-trufflehog  Skip the trufflehog secret scanner
  --no-secretlint  Skip the secretlint secret scanner
  -h, --help       Show this help`;

// `scan <path>...`: runs the deterministic scanners and exits 1 on any
// critical finding. Read-only, so it never prompts and has no --dry-run.
// Returns the process exit code.
export async function runScanCommand(argv: string[], cwd = process.cwd()): Promise<number> {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      allowPositionals: true,
      allowNegative: true,
      options: {
        trufflehog: { type: "boolean", default: true },
        secretlint: { type: "boolean", default: true },
        help: { type: "boolean", short: "h" },
      },
    });
  } catch (error) {
    rethrowAsUsageError(error);
  }
  const { values, positionals } = parsed;
  if (values.help) {
    console.log(SCAN_HELP);
    return 0;
  }
  if (positionals.length === 0) {
    throw new UsageError("scan needs at least one path.");
  }

  const gitRoot = await findGitRoot(cwd);
  const roots = await resolveScanRoots(positionals, cwd, gitRoot);
  if (roots.length === 0) {
    console.log("No existing paths to scan.");
    return 0;
  }

  const findings: Finding[] = [];
  for (const root of roots) {
    const report = await runScanners({
      rootPath: root,
      jargonSeverity: "critical",
      extraJargonTerms: await loadExtraTerms(root, gitRoot),
      skipTrufflehog: !values.trufflehog,
      skipSecretlint: !values.secretlint,
    });
    findings.push(...report.findings);
  }

  for (const finding of findings) {
    console.log(formatScanFinding(finding, cwd));
  }
  const critical = findings.filter((finding) => finding.severity === "critical").length;
  const summary = `${critical} critical, ${findings.length - critical} warning finding(s) in ${roots.length} path(s).`;
  console.log(critical > 0 ? style.red(summary) : style.green(summary));
  return critical > 0 ? 1 : 0;
}

// Maps each path to what gets scanned: the enclosing ess-* item when there is
// one, else the path itself. Missing paths (files deleted in a commit) still
// map to their item, which is scanned if it exists. Roots nested inside
// another root are dropped.
export async function resolveScanRoots(
  paths: string[],
  cwd: string,
  gitRoot: string | null,
): Promise<string[]> {
  const candidates = new Set<string>();
  for (const given of paths) {
    const abs = path.resolve(cwd, given);
    const item = gitRoot ? findEssItemRoot(toRepoRelative(gitRoot, abs)) : null;
    const root = item && gitRoot ? path.join(gitRoot, item) : abs;
    if (await pathExists(root)) candidates.add(root);
  }
  const sorted = [...candidates].sort();
  return sorted.filter(
    (root) => !sorted.some((other) => other !== root && root.startsWith(`${other}${path.sep}`)),
  );
}

// Secret findings print the rule only. Scanner messages are masked, but the
// rule is all a reader needs to find the line, so the message is left out.
export function formatScanFinding(finding: Finding, cwd: string): string {
  const location = `${path.relative(cwd, finding.file) || finding.file}:${finding.line}`;
  const rule = finding.term ?? finding.type;
  const detail = finding.type === "secret" ? "" : ` - ${finding.message}`;
  return `${location} [${finding.severity}] ${finding.source} ${rule}${detail}`;
}

async function loadExtraTerms(root: string, gitRoot: string | null): Promise<string[]> {
  const directories = new Set<string>();
  if (gitRoot) directories.add(gitRoot);
  if ((await fs.lstat(root)).isDirectory()) directories.add(root);
  const terms = new Set<string>();
  for (const directory of directories) {
    for (const term of await loadJargonOverrides(directory)) terms.add(term);
  }
  return [...terms];
}

function toRepoRelative(gitRoot: string, abs: string): string {
  const relative = path.relative(gitRoot, abs);
  if (relative.startsWith("..") || path.isAbsolute(relative)) return "";
  return relative.split(path.sep).join("/");
}

async function pathExists(target: string): Promise<boolean> {
  try {
    await fs.lstat(target);
    return true;
  } catch {
    return false;
  }
}
