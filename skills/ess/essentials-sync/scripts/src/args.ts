import { DEFAULT_JARGON_FILE, isJargonFileName } from "./jargon-list.ts";

// Bad command-line input. The CLI prints the message with a pointer to
// --help and exits 1.
export class UsageError extends Error {}

// util.parseArgs throws a TypeError coded ERR_PARSE_ARGS_* for unknown or
// malformed options; report those as usage errors and rethrow the rest.
export function rethrowAsUsageError(error: unknown): never {
  const code = (error as { code?: unknown } | null)?.code;
  if (typeof code === "string" && code.startsWith("ERR_PARSE_ARGS")) {
    throw new UsageError((error as Error).message);
  }
  throw error;
}

export const JARGON_FILE_OPTION = {
  type: "string",
  default: DEFAULT_JARGON_FILE,
} as const;

export function parseJargonFileName(value: string): string {
  if (!isJargonFileName(value)) {
    throw new UsageError(
      `--jargon-file takes a file name, not a path; it is looked up in each repo. Got: ${value}`,
    );
  }
  return value;
}

export function parseNonNegativeInteger(value: string, flag: string): number {
  if (!/^\d+$/.test(value)) {
    throw new UsageError(`${flag} expects a non-negative integer, got: ${value}`);
  }
  return Number(value);
}
