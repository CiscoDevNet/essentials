import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { isMissingBinaryError, run } from "../exec.ts";
import type { RunResult } from "../exec.ts";
import type { Finding } from "../types.ts";
import { listPublishableFiles } from "../file-set.ts";
import { PROGRAM_NAME } from "../program.ts";

// secretlint runs through npx, which caches it under ~/.npm/_npx, so the
// skill ships no node_modules. Bump both together.
export const SECRETLINT_VERSION = "9.3.4";
export const SECRETLINT_PRESET_VERSION = "9.3.4";

// Keeps each secretlint invocation's argv well under the OS limit.
const FILES_PER_INVOCATION = 500;

const DEFAULT_CONFIG_PATH = fileURLToPath(new URL("../../.secretlintrc.json", import.meta.url));

interface SecretlintJsonResult {
  filePath: string;
  messages: Array<{
    ruleId?: string;
    message: string;
    severity?: number;
    loc?: { start?: { line?: number } };
  }>;
}

export interface SecretlintScanOptions {
  configPath?: string;
  skipRootFiles?: ReadonlySet<string>;
}

export async function scanWithSecretlint(
  rootPath: string,
  options: SecretlintScanOptions = {},
): Promise<Finding[]> {
  const configPath = options.configPath ?? DEFAULT_CONFIG_PATH;
  // Pass the publishable files rather than a glob over rootPath, which would
  // also read gitignored files that never ship. secretlint rejects any path
  // outside its cwd, so it runs in the scanned directory on relative paths.
  const isFile = !(await fs.lstat(rootPath)).isDirectory();
  const cwd = isFile ? path.dirname(rootPath) : rootPath;
  const files = (await listPublishableFiles(rootPath, options.skipRootFiles)).map((relPath) =>
    isFile ? path.basename(rootPath) : relPath,
  );

  const findings: Finding[] = [];
  for (let start = 0; start < files.length; start += FILES_PER_INVOCATION) {
    const batch = files.slice(start, start + FILES_PER_INVOCATION);
    findings.push(...(await runSecretlint(configPath, cwd, batch)));
  }
  return findings;
}

async function runSecretlint(configPath: string, cwd: string, files: string[]): Promise<Finding[]> {
  // The JSON report embeds every file's source, and secretlint exits before a
  // large report has drained from a stdout pipe on macOS. It writes --output
  // synchronously, so the report is read from a file instead.
  const reportDir = await fs.mkdtemp(path.join(os.tmpdir(), `${PROGRAM_NAME}-secretlint-`));
  const reportPath = path.join(reportDir, "report.json");
  try {
    let result: RunResult;
    try {
      result = await run(
        "npx",
        [
          "--yes",
          `--package=secretlint@${SECRETLINT_VERSION}`,
          `--package=@secretlint/secretlint-rule-preset-recommend@${SECRETLINT_PRESET_VERSION}`,
          "--",
          "secretlint",
          "--secretlintrc",
          configPath,
          "--format",
          "json",
          "--maskSecrets",
          "--output",
          reportPath,
          ...files,
        ],
        { cwd },
      );
    } catch (error) {
      if (isMissingBinaryError(error)) {
        throw new Error("npx not found. secretlint runs through npx, which ships with npm.");
      }
      throw error;
    }

    // With --output, findings still exit 0. Anything else (a failed npx
    // fetch included) means secretlint never scanned, which must not read as
    // a clean result.
    if (result.exitCode !== 0) {
      const reason = lastMeaningfulLine(result.stderr || result.stdout);
      throw new Error(`secretlint exited ${result.exitCode}: ${reason}`);
    }

    // secretlint reports real paths, which differ from cwd under a symlinked
    // directory such as macOS /tmp.
    const realCwd = await fs.realpath(cwd);
    const report = await fs.readFile(reportPath, "utf8");
    return parseSecretlintOutput(report).map((finding) => ({
      ...finding,
      file: path.join(cwd, path.relative(realCwd, finding.file)),
    }));
  } finally {
    await fs.rm(reportDir, { recursive: true, force: true });
  }
}

// npm prints unrelated warnings before the real error.
function lastMeaningfulLine(output: string): string {
  const lines = output.split("\n").map((line) => line.trim()).filter((line) => line !== "");
  return lines.findLast((line) => !line.startsWith("npm warn")) ?? lines.at(-1) ?? "";
}

function parseSecretlintOutput(report: string): Finding[] {
  const trimmed = report.trim();
  if (!trimmed) return [];

  let parsed: SecretlintJsonResult[];
  try {
    parsed = JSON.parse(trimmed) as SecretlintJsonResult[];
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    throw new Error(`secretlint report is not valid JSON: ${reason}`);
  }
  const findings: Finding[] = [];
  for (const fileResult of parsed) {
    for (const message of fileResult.messages ?? []) {
      findings.push({
        file: fileResult.filePath,
        line: message.loc?.start?.line ?? 1,
        type: "secret",
        severity: "critical",
        source: "secretlint",
        message: `secretlint: ${message.message}`,
        term: message.ruleId,
      });
    }
  }
  return findings;
}
