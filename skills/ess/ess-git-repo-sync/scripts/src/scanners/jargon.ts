import type { Finding, Severity } from "../types.ts";
import { loadJargonConfig } from "../jargon-list.ts";
import { scanTextFilesByLine } from "./text-files.ts";

export interface JargonScanOptions {
  severity: Severity;
  terms: readonly string[];
  skipRootFiles?: ReadonlySet<string>;
}

export async function scanJargon(
  rootPath: string,
  options: JargonScanOptions,
): Promise<Finding[]> {
  const config = loadJargonConfig(options.terms);
  return scanTextFilesByLine(
    rootPath,
    config.patterns,
    (pattern, line) => pattern.regex.test(line),
    (pattern, filePath, lineNumber) => ({
      file: filePath,
      line: lineNumber,
      type: pattern.term.startsWith("*.") ? "internal-url" : "jargon",
      severity: options.severity,
      source: "jargon",
      message: pattern.message,
      term: pattern.term,
    }),
    { skipRootFiles: options.skipRootFiles },
  );
}
