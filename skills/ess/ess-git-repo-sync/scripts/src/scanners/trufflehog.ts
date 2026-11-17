import path from "node:path";
import { isMissingBinaryError, run } from "../exec.ts";
import type { RunResult } from "../exec.ts";
import type { Finding } from "../types.ts";
import { listPublishableFiles } from "../file-set.ts";

// Keeps each trufflehog invocation's argv well under the OS limit.
const FILES_PER_INVOCATION = 500;

// trufflehog exits 183 when it found results; anything else non-zero is a
// failed scan.
const FOUND_RESULTS_EXIT_CODE = 183;

export interface TrufflehogOptions {
  binary?: string;
  skipRootFiles?: ReadonlySet<string>;
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
  // Scan the publishable files rather than the directory: a directory scan
  // reads gitignored files (.env, .venv) that never ship.
  const files = (await listPublishableFiles(rootPath, options.skipRootFiles)).map((relPath) =>
    path.join(rootPath, relPath),
  );

  const findings: Finding[] = [];
  for (let start = 0; start < files.length; start += FILES_PER_INVOCATION) {
    const batch = files.slice(start, start + FILES_PER_INVOCATION);
    findings.push(...(await runTrufflehog(binary, batch)));
  }
  return findings;
}

async function runTrufflehog(binary: string, files: string[]): Promise<Finding[]> {
  let result: RunResult;
  try {
    result = await run(binary, ["filesystem", ...files, "--json", "--no-update"]);
  } catch (error) {
    if (isMissingBinaryError(error)) {
      throw new Error("trufflehog binary not found. Install it with `brew install trufflehog`.");
    }
    throw error;
  }

  if (result.exitCode !== 0 && result.exitCode !== FOUND_RESULTS_EXIT_CODE) {
    const reason = result.stderr.trim().split("\n")[0] ?? "";
    throw new Error(`trufflehog exited ${result.exitCode}: ${reason}`);
  }

  return parseTrufflehogOutput(result.stdout);
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
