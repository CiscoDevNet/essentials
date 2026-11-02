import type { Finding, Severity } from "../types.js";
import { scanTextFilesByLine } from "./text-files.js";

interface PiiPattern {
  name: string;
  regex: RegExp;
  message: string;
}

// Only patterns that flag real, well-defined PII signals belong here. Anything
// that looks like a "company employee ID" is org-specific and should be added
// via the jargon override file (`.essentials-sync-jargon.json`) rather than
// hardcoded here -- the previous `\b[A-Z]{3,5}\d{4,8}\b` rule false-positived
// on every ServiceNow ticket number (`INC00000001`) and ruff rule code
// (`PLR0913`) in the wild.
const PII_PATTERNS: readonly PiiPattern[] = [
  {
    // Allows the four domains IANA reserves for documentation (example.com,
    // .net, .org, .edu) and any subdomain of them (bob@corp.example.com), in
    // any case. The domain must end there, so a lookalike such as
    // x@example.com.evil.org is still flagged. Other reserved names (.example,
    // .invalid, .test) and registrable ones (example.io) are flagged on
    // purpose: placeholders stick to the four.
    name: "email",
    regex: /\b[A-Za-z0-9._%+-]+@(?!(?:[A-Za-z0-9-]+\.)*example\.(?:com|org|net|edu)(?!\.?[A-Za-z0-9-]))[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/gi,
    message: "Email address that is not on example.com, example.net, example.org, or example.edu.",
  },
  {
    name: "phone",
    regex: /\b(?:\+?1[\s.-]?)?\(?[2-9]\d{2}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b/g,
    message: "Possible phone number.",
  },
  {
    name: "ssn",
    regex: /\b\d{3}-\d{2}-\d{4}\b/g,
    message: "Possible US Social Security Number.",
  },
];

export interface PiiScanOptions {
  severity: Severity;
}

export async function scanPii(
  rootPath: string,
  options: PiiScanOptions,
): Promise<Finding[]> {
  return scanTextFilesByLine(
    rootPath,
    PII_PATTERNS,
    (pattern, line) => {
      // Patterns are global regexes, so reset lastIndex before each test.
      pattern.regex.lastIndex = 0;
      return pattern.regex.test(line);
    },
    (pattern, filePath, lineNumber) => ({
      file: filePath,
      line: lineNumber,
      type: "pii",
      severity: options.severity,
      source: "pii",
      message: pattern.message,
      term: pattern.name,
    }),
  );
}
