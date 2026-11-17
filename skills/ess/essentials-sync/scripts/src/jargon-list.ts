export interface JargonPattern {
  term: string;
  regex: RegExp;
  message: string;
}

const wordBoundary = (word: string): RegExp =>
  new RegExp(`\\b${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");

const hostnameSuffix = (suffix: string): RegExp =>
  new RegExp(`[a-z0-9-]+\\.${suffix.replace(/\./g, "\\.")}`, "i");

// The wordlist lives in the repos, not here: each repo lists its company's
// terms in a file with this name at its root (or at an item's root).
export const DEFAULT_JARGON_FILE = "jargon.json";

// The jargon file is looked up by name at several locations, so the name may
// not contain a directory.
export function isJargonFileName(name: string): boolean {
  return name !== "" && name !== "." && name !== ".." && !/[\\/]/.test(name);
}

export interface JargonConfig {
  patterns: JargonPattern[];
}

// Exceptions to the wordlist. `paths` are repo-relative globs (`*`, `**`, `?`)
// whose contents are never flagged; `text` entries are literal strings that are
// blanked out of a line before matching, so an allowed hostname on the same
// line as a forbidden one still leaves the forbidden one flagged.
export interface JargonAllowList {
  paths: string[];
  text: string[];
}

// A parsed jargon file. Accepts a flat array of terms or
// `{ "terms": [...], "allow": { "paths": [...], "text": [...] } }`.
export interface JargonOverrides {
  terms: string[];
  allow: JargonAllowList;
}

const toStrings = (value: unknown): string[] =>
  Array.isArray(value)
    ? value.filter((entry): entry is string => typeof entry === "string")
    : [];

export function parseJargonOverrides(parsed: unknown): JargonOverrides {
  if (Array.isArray(parsed)) {
    return { terms: toStrings(parsed), allow: { paths: [], text: [] } };
  }
  if (!parsed || typeof parsed !== "object") {
    return { terms: [], allow: { paths: [], text: [] } };
  }
  const { terms, allow } = parsed as { terms?: unknown; allow?: unknown };
  const allowObject = (allow && typeof allow === "object" ? allow : {}) as {
    paths?: unknown;
    text?: unknown;
  };
  return {
    terms: toStrings(terms),
    allow: { paths: toStrings(allowObject.paths), text: toStrings(allowObject.text) },
  };
}

const escapeRegExp = (value: string): string =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function globToRegExp(glob: string): RegExp {
  let source = "";
  for (let i = 0; i < glob.length; i += 1) {
    const char = glob[i] ?? "";
    if (char === "*" && glob[i + 1] === "*") {
      // `**/` matches zero or more whole directories; a trailing `**` matches
      // everything below.
      const hasSlash = glob[i + 2] === "/";
      source += hasSlash ? "(?:.*/)?" : ".*";
      i += hasSlash ? 2 : 1;
    } else if (char === "*") {
      source += "[^/]*";
    } else if (char === "?") {
      source += "[^/]";
    } else {
      source += escapeRegExp(char);
    }
  }
  return new RegExp(`^${source}$`);
}

export function isAllowedPath(relativePath: string, allowPaths: readonly string[]): boolean {
  const normalized = relativePath.split("\\").join("/");
  return allowPaths.some((glob) => globToRegExp(glob).test(normalized));
}

export function maskAllowedText(line: string, allowText: readonly string[]): string {
  let masked = line;
  for (const text of allowText) {
    if (text) {
      masked = masked.replace(new RegExp(escapeRegExp(text), "gi"), " ");
    }
  }
  return masked;
}

export function findJargonTerms(
  line: string,
  config: JargonConfig,
  allowText: readonly string[] = [],
): JargonPattern[] {
  const masked = maskAllowedText(line, allowText);
  return config.patterns.filter((pattern) => pattern.regex.test(masked));
}

// Builds the patterns for a wordlist. A term starting with `*.` matches any
// hostname under that suffix; any other term matches as a whole word, in any
// case. Blank terms are dropped.
export function loadJargonConfig(terms: readonly string[]): JargonConfig {
  const patterns: JargonPattern[] = [];
  for (const raw of terms) {
    const trimmed = raw.trim();
    if (!trimmed) continue;
    if (trimmed.startsWith("*.")) {
      patterns.push({
        term: trimmed,
        regex: hostnameSuffix(trimmed.slice(2)),
        message: `Contains hostname matching ${trimmed}.`,
      });
    } else {
      patterns.push({
        term: trimmed,
        regex: wordBoundary(trimmed),
        message: `Contains jargon term '${trimmed}'.`,
      });
    }
  }
  return { patterns };
}
