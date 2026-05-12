import { promises as fs } from "node:fs";
import path from "node:path";
import type { Finding, Severity } from "../types.js";
import { loadJargonConfig, type JargonConfig } from "../jargon-list.js";

const DEFAULT_BINARY_EXTENSIONS = new Set([
  ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".tar", ".gz",
  ".bz2", ".xz", ".7z", ".woff", ".woff2", ".eot", ".ttf", ".otf", ".ico",
  ".so", ".dylib", ".dll", ".class", ".jar", ".wasm", ".bin",
]);

const SKIP_DIRECTORIES = new Set([
  "node_modules", ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
  ".ruff_cache", ".mypy_cache", "dist", "build", ".pulumi",
]);

export interface JargonScanOptions {
  severity: Severity;
  extraTerms?: string[];
}

export async function scanJargon(
  rootPath: string,
  options: JargonScanOptions,
): Promise<Finding[]> {
  const config = loadJargonConfig(options.extraTerms);
  const findings: Finding[] = [];
  for await (const filePath of walkTextFiles(rootPath)) {
    const content = await fs.readFile(filePath, "utf8");
    findings.push(...scanContent(filePath, content, config, options.severity));
  }
  return findings;
}

function scanContent(
  filePath: string,
  content: string,
  config: JargonConfig,
  severity: Severity,
): Finding[] {
  const lines = content.split(/\r?\n/);
  const found: Finding[] = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i] ?? "";
    for (const pattern of config.patterns) {
      if (pattern.regex.test(line)) {
        found.push({
          file: filePath,
          line: i + 1,
          type: pattern.term.startsWith("*.") ? "internal-url" : "jargon",
          severity,
          source: "jargon",
          message: pattern.message,
          term: pattern.term,
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
        if (DEFAULT_BINARY_EXTENSIONS.has(ext)) continue;
        const stat = await fs.stat(fullPath);
        if (stat.size > 5 * 1024 * 1024) continue;
        yield fullPath;
      }
    }
  }
}
