import { promises as fs } from "node:fs";
import path from "node:path";
import { parseJargonOverrides } from "./jargon-list.ts";

export interface LoadedJargon {
  terms: string[];
  // `allow.text` from every file read: literal strings, such as a public org
  // name, that are blanked out of a line before the terms are matched.
  allowText: string[];
  // Every path the file was looked for at, read or not, for error messages.
  searchedPaths: string[];
  readPaths: string[];
}

// Reads <location>/<fileName> at each location and merges the terms and the
// allowed text. A
// location that is a file (a single-file item) reads the file beside it;
// null and repeated locations are skipped. A missing file contributes
// nothing. A file that exists but cannot be parsed throws: a broken wordlist
// must not quietly weaken the scan.
export async function loadJargonTerms(
  locations: ReadonlyArray<string | null | undefined>,
  fileName: string,
): Promise<LoadedJargon> {
  const directories: string[] = [];
  for (const location of locations) {
    if (!location) continue;
    const directory = await jargonDirectory(location);
    if (!directories.includes(directory)) directories.push(directory);
  }

  const terms = new Set<string>();
  const allowText = new Set<string>();
  const searchedPaths: string[] = [];
  const readPaths: string[] = [];
  for (const directory of directories) {
    const configPath = path.join(directory, fileName);
    searchedPaths.push(configPath);
    let raw: string;
    try {
      raw = await fs.readFile(configPath, "utf8");
    } catch (error) {
      if (isNotFoundError(error)) continue;
      throw error;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw) as unknown;
    } catch (error) {
      throw new Error(`${configPath} is not valid JSON: ${(error as Error).message}`);
    }
    readPaths.push(configPath);
    const overrides = parseJargonOverrides(parsed);
    for (const term of overrides.terms) {
      if (term.trim()) terms.add(term.trim());
    }
    for (const text of overrides.allow.text) {
      if (text) allowText.add(text);
    }
  }
  return { terms: [...terms], allowText: [...allowText], searchedPaths, readPaths };
}

// Scans fail closed: with no wordlist, a clean jargon scan proves nothing.
export function requireJargonTerms(loaded: LoadedJargon, fileName: string): string[] {
  if (loaded.terms.length > 0) return loaded.terms;
  const searched = loaded.searchedPaths.length > 0 ? loaded.searchedPaths.join(", ") : "(nowhere)";
  throw new Error(
    `No jargon terms found. Looked for ${fileName} at: ${searched}. List the company's `
      + "terms in that file at the source repo root (see references/cli.md for the format), "
      + "or name a different file with --jargon-file.",
  );
}

async function jargonDirectory(location: string): Promise<string> {
  const resolved = path.resolve(location);
  try {
    const stat = await fs.stat(resolved);
    if (stat.isFile()) return path.dirname(resolved);
  } catch (error) {
    if (!isNotFoundError(error)) throw error;
  }
  return resolved;
}

function isNotFoundError(error: unknown): boolean {
  return Boolean(
    error && typeof error === "object" && (error as { code?: string }).code === "ENOENT",
  );
}
