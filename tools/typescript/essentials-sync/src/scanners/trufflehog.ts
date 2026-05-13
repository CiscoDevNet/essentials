import { execa } from "execa";
import type { Finding } from "../types.js";

export interface TrufflehogOptions {
  binary?: string;
}

interface TrufflehogJsonLine {
  SourceMetadata?: {
    Data?: {
      Filesystem?: {
        file?: string;
        line?: number;
      };
    };
  };
  DetectorName?: string;
  Verified?: boolean;
  Raw?: string;
}

export async function scanWithTrufflehog(
  rootPath: string,
  options: TrufflehogOptions = {},
): Promise<Finding[]> {
  const binary = options.binary ?? "trufflehog";

  let result;
  try {
    result = await execa(
      binary,
      ["filesystem", rootPath, "--json", "--no-update"],
      {
        reject: false,
        stripFinalNewline: false,
      },
    );
  } catch (error) {
    if (isMissingBinaryError(error)) {
      throw new Error(
        "trufflehog binary not found. Install it with `brew install trufflehog` "
          + "or pass --trufflehog-binary <path>.",
      );
    }
    throw error;
  }

  if (result.exitCode !== 0 && result.exitCode !== 183) {
    if (result.stderr && result.stderr.toLowerCase().includes("not found")) {
      throw new Error(
        "trufflehog binary not found. Install it with `brew install trufflehog`.",
      );
    }
  }

  return parseTrufflehogOutput(result.stdout ?? "");
}

function isMissingBinaryError(error: unknown): boolean {
  if (error && typeof error === "object") {
    const code = (error as { code?: string }).code;
    return code === "ENOENT";
  }
  return false;
}

function parseTrufflehogOutput(stdout: string): Finding[] {
  const lines = stdout.split(/\r?\n/).filter((line) => line.trim() !== "");
  const findings: Finding[] = [];
  for (const rawLine of lines) {
    let parsed: TrufflehogJsonLine;
    try {
      parsed = JSON.parse(rawLine) as TrufflehogJsonLine;
    } catch {
      continue;
    }
    const file = parsed.SourceMetadata?.Data?.Filesystem?.file;
    const lineNumber = parsed.SourceMetadata?.Data?.Filesystem?.line ?? 1;
    if (!file) continue;
    findings.push({
      file,
      line: lineNumber,
      type: "secret",
      severity: "critical",
      source: "trufflehog",
      message: `Secret detected by trufflehog: detector=${parsed.DetectorName ?? "unknown"}, verified=${
        parsed.Verified ? "true" : "false"
      }`,
      term: parsed.DetectorName,
    });
  }
  return findings;
}
