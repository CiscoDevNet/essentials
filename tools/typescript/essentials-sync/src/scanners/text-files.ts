import { promises as fs } from "node:fs";
import path from "node:path";
import { globbyStream } from "globby";
import type { Finding } from "../types.js";

// Always skipped, even when the scanned tree has no .gitignore. These are
// caches, build output, and VCS/dependency directories that never carry
// meaningful findings.
export const HARD_SKIP_DIRECTORIES = [
  "node_modules", ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
  ".ruff_cache", ".mypy_cache", "dist", "build", ".pulumi",
];

const BINARY_EXTENSIONS = [
  ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".tar", ".gz",
  ".bz2", ".xz", ".7z", ".woff", ".woff2", ".eot", ".ttf", ".otf", ".ico",
  ".so", ".dylib", ".dll", ".class", ".jar", ".wasm", ".bin",
];

const MAX_FILE_BYTES = 5 * 1024 * 1024;

// True when walkTextFiles would have passed over this file: a binary extension
// or past the size cap. Callers that copy files rather than scan them use this
// to report what left the source repo without being read.
export async function isUnscannableTextFile(filePath: string): Promise<boolean> {
  if (BINARY_EXTENSIONS.includes(path.extname(filePath).toLowerCase())) {
    return true;
  }
  const stat = await fs.stat(filePath);
  return stat.size > MAX_FILE_BYTES;
}

// Yields absolute paths of candidate text files under rootPath. Traversal,
// .gitignore handling, and directory/extension skipping are delegated to
// globby; the only thing globby cannot express is the per-file size cap, so
// oversized files are filtered with a stat after globbing.
export async function* walkTextFiles(rootPath: string): AsyncGenerator<string> {
  const ignore = [
    ...HARD_SKIP_DIRECTORIES.map((dir) => `**/${dir}/**`),
    ...BINARY_EXTENSIONS.map((ext) => `**/*${ext}`),
    "**/tmp-*",
    "**/tmp.*",
  ];
  const stream = globbyStream("**/*", {
    cwd: rootPath,
    absolute: true,
    dot: true,
    gitignore: true,
    ignore,
  });
  for await (const entry of stream) {
    const filePath = entry as string;
    const stat = await fs.stat(filePath);
    if (stat.size > MAX_FILE_BYTES) continue;
    yield filePath;
  }
}

// Runs a set of line-oriented patterns over every text file under rootPath.
// `test` decides whether a pattern matches a given line; `toFinding` builds the
// Finding for a match. This centralizes the read/split/loop that both the pii
// and jargon scanners would otherwise duplicate.
export async function scanTextFilesByLine<P>(
  rootPath: string,
  patterns: readonly P[],
  test: (pattern: P, line: string) => boolean,
  toFinding: (pattern: P, filePath: string, lineNumber: number) => Finding,
): Promise<Finding[]> {
  const findings: Finding[] = [];
  for await (const filePath of walkTextFiles(rootPath)) {
    const content = await fs.readFile(filePath, "utf8");
    const lines = content.split(/\r?\n/);
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i] ?? "";
      for (const pattern of patterns) {
        if (test(pattern, line)) {
          findings.push(toFinding(pattern, filePath, i + 1));
        }
      }
    }
  }
  return findings;
}
