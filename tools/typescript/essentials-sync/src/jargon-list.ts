export interface JargonPattern {
  term: string;
  regex: RegExp;
  message: string;
}

const wordBoundary = (word: string): RegExp =>
  new RegExp(`\\b${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");

const hostnameSuffix = (suffix: string): RegExp =>
  new RegExp(`[a-z0-9-]+\\.${suffix.replace(/\./g, "\\.")}`, "i");

export const DEFAULT_JARGON_PATTERNS: readonly JargonPattern[] = [
  {
    term: "cisco",
    regex: wordBoundary("cisco"),
    message: "Contains the company name 'cisco' (case-insensitive).",
  },
  {
    term: "*.cisco.com",
    regex: hostnameSuffix("cisco.com"),
    message: "Contains an internal Cisco hostname.",
  },
  {
    term: "myid",
    regex: wordBoundary("myid"),
    message: "References 'myid' identity service.",
  },
  {
    term: "cec",
    regex: wordBoundary("cec"),
    message: "References 'cec' (Cisco employee credential).",
  },
  {
    term: "cisco-ceto",
    regex: wordBoundary("cisco-ceto"),
    message: "References internal cisco-ceto org.",
  },
  {
    term: "honeycomb",
    regex: wordBoundary("honeycomb"),
    message: "References the internal 'honeycomb' repo name.",
  },
];

export interface JargonConfig {
  patterns: JargonPattern[];
}

export function loadJargonConfig(extraTerms: string[] = []): JargonConfig {
  const extras: JargonPattern[] = extraTerms.map((raw) => {
    const trimmed = raw.trim();
    if (trimmed.startsWith("*.")) {
      const suffix = trimmed.slice(2);
      return {
        term: trimmed,
        regex: hostnameSuffix(suffix),
        message: `Contains hostname matching ${trimmed}.`,
      };
    }
    return {
      term: trimmed,
      regex: wordBoundary(trimmed),
      message: `Contains custom jargon term '${trimmed}'.`,
    };
  });
  return {
    patterns: [...DEFAULT_JARGON_PATTERNS, ...extras],
  };
}
