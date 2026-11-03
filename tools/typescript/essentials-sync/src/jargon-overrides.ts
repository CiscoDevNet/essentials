import { promises as fs } from "node:fs";
import path from "node:path";
import chalk from "chalk";
import { parseJargonOverrides } from "./jargon-list.js";

export const JARGON_OVERRIDES_FILE = ".essentials-sync-jargon.json";

// Reads extra jargon terms from <directory>/.essentials-sync-jargon.json. A
// missing file means no extra terms; an unreadable one is warned about and
// treated the same way so a typo never blocks a scan.
export async function loadJargonOverrides(directory: string): Promise<string[]> {
  const configPath = path.join(directory, JARGON_OVERRIDES_FILE);
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
