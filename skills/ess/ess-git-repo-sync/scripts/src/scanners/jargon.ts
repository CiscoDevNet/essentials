import type { Finding, Severity } from "../types.ts";
import { loadJargonConfig, maskAllowedText } from "../jargon-list.ts";
import { scanTextFilesByLine } from "./text-files.ts";

export interface JargonScanOptions {
  severity: Severity;
  terms: readonly string[];
  allowText?: readonly string[];
  skipRootFiles?: ReadonlySet<string>;
}

export async function scanJargon(
  rootPath: string,
  options: JargonScanOptions,
): Promise<Finding[]> {
  const config = loadJargonConfig(options.terms);
  const allowText = options.allowText ?? [];
  return scanTextFilesByLine(
    rootPath,
    config.patterns,
    (pattern, line) => pattern.regex.test(maskAllowedText(line, allowText)),
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
