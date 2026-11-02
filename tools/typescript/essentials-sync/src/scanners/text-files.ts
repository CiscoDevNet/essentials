import { promises as fs } from "node:fs";
import path from "node:path";
import type { Finding } from "../types.js";
import { listPublishableFiles } from "../file-set.js";

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

// Yields absolute paths of the publishable text files under rootPath: the
// shared file set minus symlinks, binary extensions, and oversized files.
export async function* walkTextFiles(rootPath: string): AsyncGenerator<string> {
  for (const relPath of await listPublishableFiles(rootPath)) {
    const filePath = path.join(rootPath, relPath);
    const stat = await fs.lstat(filePath);
    if (!stat.isFile()) continue;
    if (await isUnscannableTextFile(filePath)) continue;
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
