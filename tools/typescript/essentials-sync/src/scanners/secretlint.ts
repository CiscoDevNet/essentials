import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { execa } from "execa";
import type { Finding } from "../types.js";
import { listPublishableFiles } from "../file-set.js";

// Keeps each secretlint invocation's argv well under the OS limit.
const FILES_PER_INVOCATION = 500;

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
}

export async function scanWithSecretlint(
  rootPath: string,
  options: SecretlintScanOptions = {},
): Promise<Finding[]> {
  const packageRoot = packageRootPath();
  const configPath = options.configPath ?? path.join(packageRoot, ".secretlintrc.json");
  // Pass the publishable files rather than a glob over rootPath, which would
  // also read gitignored files that never ship. secretlint rejects any path
  // outside its cwd, so it runs in the scanned directory on relative paths.
  const isFile = !(await fs.lstat(rootPath)).isDirectory();
  const cwd = isFile ? path.dirname(rootPath) : rootPath;
  const files = (await listPublishableFiles(rootPath)).map((relPath) =>
    isFile ? path.basename(rootPath) : relPath,
  );

  const findings: Finding[] = [];
  for (let start = 0; start < files.length; start += FILES_PER_INVOCATION) {
    const batch = files.slice(start, start + FILES_PER_INVOCATION);
    findings.push(...(await runSecretlint(packageRoot, configPath, cwd, batch)));
  }
  return findings;
}

async function runSecretlint(
  packageRoot: string,
  configPath: string,
  cwd: string,
  files: string[],
): Promise<Finding[]> {
  // The JSON report embeds every file's source, and secretlint exits before a
  // large report has drained from a stdout pipe on macOS. It writes --output
  // synchronously, so the report is read from a file instead.
  const reportDir = await fs.mkdtemp(path.join(os.tmpdir(), "essentials-sync-secretlint-"));
  const reportPath = path.join(reportDir, "report.json");
  try {
    let result;
    try {
      result = await execa(
        "secretlint",
        [
          "--secretlintrc",
          configPath,
          "--format",
          "json",
          "--maskSecrets",
          "--output",
          reportPath,
          ...files,
        ],
        {
          reject: false,
          cwd,
          preferLocal: true,
          localDir: packageRoot,
        },
      );
    } catch (error) {
      if (isMissingBinaryError(error)) {
        throw new Error(
          "secretlint not installed in this package. Run `npm install` first.",
        );
      }
      throw error;
    }

    // With --output, findings still exit 0. Anything else means secretlint
    // never scanned, which must not read as a clean result.
    if (result.exitCode !== 0) {
      const reason = (result.stderr || result.stdout || "").trim().split("\n")[0];
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

function isMissingBinaryError(error: unknown): boolean {
  if (error && typeof error === "object") {
    const code = (error as { code?: string }).code;
    return code === "ENOENT";
  }
  return false;
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

function packageRootPath(): string {
  return path.resolve(new URL("../..", import.meta.url).pathname);
}
