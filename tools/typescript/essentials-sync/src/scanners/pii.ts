import { promises as fs } from "node:fs";
import path from "node:path";
import type { Finding, Severity } from "../types.js";

const SKIP_DIRECTORIES = new Set([
  "node_modules", ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
  ".ruff_cache", ".mypy_cache", "dist", "build", ".pulumi",
]);

const BINARY_EXTENSIONS = new Set([
  ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".tar", ".gz",
  ".bz2", ".xz", ".7z", ".woff", ".woff2", ".eot", ".ttf", ".otf", ".ico",
  ".so", ".dylib", ".dll", ".class", ".jar", ".wasm", ".bin",
]);

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
    name: "email",
    regex: /\b[A-Za-z0-9._%+-]+@(?!example\.(?:com|org|net))[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,
    message: "Email address that is not on a documented example domain.",
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
  const findings: Finding[] = [];
  for await (const filePath of walkTextFiles(rootPath)) {
    const content = await fs.readFile(filePath, "utf8");
    findings.push(...scanContent(filePath, content, options.severity));
  }
  return findings;
}

function scanContent(filePath: string, content: string, severity: Severity): Finding[] {
  const lines = content.split(/\r?\n/);
  const found: Finding[] = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i] ?? "";
    for (const pattern of PII_PATTERNS) {
      pattern.regex.lastIndex = 0;
      if (pattern.regex.test(line)) {
        found.push({
          file: filePath,
          line: i + 1,
          type: "pii",
          severity,
          source: "pii",
          message: pattern.message,
          term: pattern.name,
        });
      }
    }
  }
  return found;
}

async function* walkTextFiles(rootPath: string): AsyncGenerator<string> {
  const stack: string[] = [rootPath];
  while (stack.length > 0) {
    const current = stack.pop();
    if (!current) continue;
    let entries;
    try {
      entries = await fs.readdir(current, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        if (SKIP_DIRECTORIES.has(entry.name)) continue;
        stack.push(fullPath);
      } else if (entry.isFile()) {
        const ext = path.extname(entry.name).toLowerCase();
        if (BINARY_EXTENSIONS.has(ext)) continue;
        const stat = await fs.stat(fullPath);
        if (stat.size > 5 * 1024 * 1024) continue;
        yield fullPath;
      }
    }
  }
}
