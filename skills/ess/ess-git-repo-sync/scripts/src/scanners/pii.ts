import path from "node:path";
import type { Finding, Severity } from "../types.ts";
import { scanTextFilesByLine } from "./text-files.ts";

interface PiiPattern {
  name: string;
  regex: RegExp;
  message: string;
}

// Only patterns that flag real, well-defined PII signals belong here. Anything
// that looks like a "company employee ID" is org-specific and belongs in the
// repo's jargon file (`jargon.json`) rather than hardcoded here -- the previous `\b[A-Z]{3,5}\d{4,8}\b` rule false-positived
// on every ServiceNow ticket number (`INC00000001`) and ruff rule code
// (`PLR0913`) in the wild.
const PII_PATTERNS: readonly PiiPattern[] = [
  {
    // Allows the four domains IANA reserves for documentation (example.com,
    // .net, .org, .edu) and any subdomain of them (bob@corp.example.com), plus
    // any name under the reserved TLDs .example, .invalid, and .test, in any
    // case. The reserved name must end the address, so a lookalike domain such
    // as example.com.evil.org or test.com is still flagged, as is a
    // registrable name such as example.io.
    name: "email",
    regex: /\b[A-Za-z0-9._%+-]+@(?!(?:[A-Za-z0-9-]+\.)*(?:example\.(?:com|org|net|edu)|example|invalid|test)(?!\.?[A-Za-z0-9-]))[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/gi,
    message:
      "Email address that is not on example.com, example.net, example.org, or example.edu,"
      + " or under the .example, .invalid, or .test TLDs.",
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

// Lock files are generated from registry metadata, which carries upstream
// maintainers' public addresses (npm deprecation notices, for one). The jargon
// and secret scanners still read them, so a private registry host is caught.
const LOCK_FILE_NAMES: ReadonlySet<string> = new Set([
  "Cargo.lock",
  "Gemfile.lock",
  "npm-shrinkwrap.json",
  "package-lock.json",
  "pnpm-lock.yaml",
  "poetry.lock",
  "uv.lock",
  "yarn.lock",
]);

export interface PiiScanOptions {
  severity: Severity;
  skipRootFiles?: ReadonlySet<string>;
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
    {
      skipRootFiles: options.skipRootFiles,
      skipFile: (filePath) => LOCK_FILE_NAMES.has(path.basename(filePath)),
    },
  );
}
