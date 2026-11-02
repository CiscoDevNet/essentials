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
  // also read gitignored files that never ship.
  const files = (await listPublishableFiles(rootPath)).map((relPath) => path.join(rootPath, relPath));

  const findings: Finding[] = [];
  for (let start = 0; start < files.length; start += FILES_PER_INVOCATION) {
    const batch = files.slice(start, start + FILES_PER_INVOCATION);
    findings.push(...(await runSecretlint(packageRoot, configPath, batch)));
  }
  return findings;
}

async function runSecretlint(
  packageRoot: string,
  configPath: string,
  files: string[],
): Promise<Finding[]> {
  let result;
  try {
    result = await execa(
      "npx",
      [
        "--no-install",
        "secretlint",
        "--secretlintrc",
        configPath,
        "--format",
        "json",
        "--maskSecrets",
        ...files,
      ],
      {
        reject: false,
        cwd: packageRoot,
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

  return parseSecretlintOutput(result.stdout ?? "");
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
