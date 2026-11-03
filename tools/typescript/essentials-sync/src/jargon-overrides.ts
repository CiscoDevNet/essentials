import { promises as fs } from "node:fs";
import path from "node:path";
import chalk from "chalk";
import { parseJargonOverrides } from "./jargon-list.js";

export const JARGON_OVERRIDES_FILE = ".essentials-sync-jargon.json";

// Reads extra jargon terms from <anchor>/.essentials-sync-jargon.json. A
// single-file source (an instructions/ess item) loads the file beside it.
// A missing file means no extra terms; an unreadable one is warned about and
// treated the same way so a typo never blocks a scan.
export async function loadJargonOverrides(anchor: string): Promise<string[]> {
  const configPath = path.join(await jargonDirectory(anchor), JARGON_OVERRIDES_FILE);
  try {
    const raw = await fs.readFile(configPath, "utf8");
    return parseJargonOverrides(JSON.parse(raw) as unknown).terms;
  } catch (error) {
    if (error instanceof Error && "code" in error && (error as { code?: string }).code === "ENOENT") {
      return [];
    }
    console.warn(
      chalk.yellow(`[jargon] could not read ${configPath}: ${(error as Error).message}`),
    );
    return [];
  }
}

async function jargonDirectory(anchor: string): Promise<string> {
  try {
    const stat = await fs.stat(anchor);
    if (stat.isFile()) return path.dirname(anchor);
  } catch (error) {
    if (!isNotFoundError(error)) throw error;
  }
  return anchor;
}

function isNotFoundError(error: unknown): boolean {
  return Boolean(
    error && typeof error === "object" && (error as { code?: string }).code === "ENOENT",
  );
}
