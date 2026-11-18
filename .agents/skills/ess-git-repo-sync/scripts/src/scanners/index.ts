import type { Finding, ScanReport, Severity } from "../types.ts";
import { DEFAULT_JARGON_FILE } from "../jargon-list.ts";
import { scanJargon } from "./jargon.ts";
import { scanPii } from "./pii.ts";
import { scanWithTrufflehog } from "./trufflehog.ts";
import { scanWithSecretlint } from "./secretlint.ts";

export interface RunScannersOptions {
  rootPath: string;
  jargonSeverity: Severity;
  jargonTerms: readonly string[];
  jargonAllowText?: readonly string[];
  // The wordlist file at rootPath is skipped: it lists the very terms the
  // jargon scanner looks for, and it is never published.
  jargonFile?: string;
  skipTrufflehog?: boolean;
  skipSecretlint?: boolean;
}

export async function runScanners({
  rootPath,
  jargonSeverity,
  jargonTerms,
  jargonAllowText = [],
  jargonFile = DEFAULT_JARGON_FILE,
  skipTrufflehog,
  skipSecretlint,
}: RunScannersOptions): Promise<ScanReport> {
  const start = Date.now();
  const all: Finding[] = [];
  const skipRootFiles: ReadonlySet<string> = new Set([jargonFile]);

  const tasks: Array<Promise<Finding[]>> = [];

  if (!skipTrufflehog) {
    tasks.push(
      scanWithTrufflehog(rootPath, { skipRootFiles }).catch((error: unknown) => {
        return [makeScannerErrorFinding("trufflehog", error, rootPath)];
      }),
    );
  }
  if (!skipSecretlint) {
    tasks.push(
      scanWithSecretlint(rootPath, { skipRootFiles }).catch((error: unknown) => {
        return [makeScannerErrorFinding("secretlint", error, rootPath)];
      }),
    );
  }
  tasks.push(scanJargon(rootPath, {
    severity: jargonSeverity,
    terms: jargonTerms,
    allowText: jargonAllowText,
    skipRootFiles,
  }));
  tasks.push(scanPii(rootPath, { severity: "critical", skipRootFiles }));

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
