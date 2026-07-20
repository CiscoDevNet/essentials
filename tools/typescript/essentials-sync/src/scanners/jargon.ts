import type { Finding, Severity } from "../types.js";
import { loadJargonConfig } from "../jargon-list.js";
import { scanTextFilesByLine } from "./text-files.js";

export interface JargonScanOptions {
  severity: Severity;
  extraTerms?: string[];
}

export async function scanJargon(
  rootPath: string,
  options: JargonScanOptions,
): Promise<Finding[]> {
  const config = loadJargonConfig(options.extraTerms);
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
  );
}
