import path from "node:path";
import { execa } from "execa";
import type { Finding } from "../types.js";

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
        `${rootPath}/**/*`,
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
