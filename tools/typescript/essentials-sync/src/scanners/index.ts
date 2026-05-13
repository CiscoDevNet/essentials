import type { Finding, ScanReport, Severity } from "../types.js";
import { scanJargon } from "./jargon.js";
import { scanPii } from "./pii.js";
import { scanWithTrufflehog } from "./trufflehog.js";
import { scanWithSecretlint } from "./secretlint.js";

export interface RunScannersOptions {
  rootPath: string;
  jargonSeverity: Severity;
  extraJargonTerms?: string[];
  skipTrufflehog?: boolean;
  skipSecretlint?: boolean;
}

export async function runScanners({
  rootPath,
  jargonSeverity,
  extraJargonTerms,
  skipTrufflehog,
  skipSecretlint,
}: RunScannersOptions): Promise<ScanReport> {
  const start = Date.now();
  const all: Finding[] = [];

  const tasks: Array<Promise<Finding[]>> = [];

  if (!skipTrufflehog) {
    tasks.push(
      scanWithTrufflehog(rootPath).catch((error: unknown) => {
        return [makeScannerErrorFinding("trufflehog", error, rootPath)];
      }),
    );
  }
  if (!skipSecretlint) {
    tasks.push(
      scanWithSecretlint(rootPath).catch((error: unknown) => {
        return [makeScannerErrorFinding("secretlint", error, rootPath)];
      }),
    );
  }
  tasks.push(
    scanJargon(rootPath, {
      severity: jargonSeverity,
      extraTerms: extraJargonTerms,
    }),
  );
  tasks.push(scanPii(rootPath, { severity: "critical" }));

  const results = await Promise.all(tasks);
  for (const findings of results) {
    all.push(...findings);
  }

  return {
    findings: all,
    scannedPaths: [rootPath],
    durationMs: Date.now() - start,
  };
}

function makeScannerErrorFinding(
  scanner: "trufflehog" | "secretlint",
  error: unknown,
  rootPath: string,
): Finding {
  const message = error instanceof Error ? error.message : String(error);
  return {
    file: rootPath,
    line: 1,
    type: "other",
    severity: "warning",
    source: scanner,
    message: `Scanner '${scanner}' failed: ${message}`,
  };
}

export function hasCriticalFindings(report: ScanReport): boolean {
  return report.findings.some((finding) => finding.severity === "critical");
}

export function formatFindings(report: ScanReport): string {
  if (report.findings.length === 0) {
    return "No findings.";
  }
  const lines: string[] = [];
  for (const finding of report.findings) {
    lines.push(
      `[${finding.severity}] ${finding.source}: ${finding.file}:${finding.line}`
        + ` - ${finding.message}`
        + (finding.term ? ` (term=${finding.term})` : ""),
    );
  }
  return lines.join("\n");
}
