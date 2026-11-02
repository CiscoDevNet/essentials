import { promises as fs } from "node:fs";
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
  let result;
  try {
    result = await execa(
      "secretlint",
      ["--secretlintrc", configPath, "--format", "json", "--maskSecrets", ...files],
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

  // 0 is clean and 1 is findings. Anything else means secretlint never
  // scanned, which must not read as a clean result.
  if (result.exitCode !== 0 && result.exitCode !== 1) {
    const reason = (result.stderr || result.stdout || "").trim().split("\n")[0];
    throw new Error(`secretlint exited ${result.exitCode}: ${reason}`);
  }

  // secretlint reports real paths, which differ from cwd under a symlinked
  // directory such as macOS /tmp.
  const realCwd = await fs.realpath(cwd);
  return parseSecretlintOutput(result.stdout ?? "").map((finding) => ({
    ...finding,
    file: path.join(cwd, path.relative(realCwd, finding.file)),
  }));
}

function isMissingBinaryError(error: unknown): boolean {
  if (error && typeof error === "object") {
    const code = (error as { code?: string }).code;
    return code === "ENOENT";
  }
  return false;
}

function parseSecretlintOutput(stdout: string): Finding[] {
  const trimmed = stdout.trim();
  if (!trimmed) return [];

  let parsed: SecretlintJsonResult[];
  try {
    parsed = JSON.parse(trimmed) as SecretlintJsonResult[];
  } catch {
    return [];
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
