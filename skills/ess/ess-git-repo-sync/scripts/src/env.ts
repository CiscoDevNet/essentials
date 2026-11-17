import { existsSync } from "node:fs";
import path from "node:path";
import { configDirectory } from "./program.ts";

// .env files the CLI reads, first match wins per variable: the current
// directory, then the user config directory. Never one next to the code,
// which a skill installer would copy along with the skill.
export function envFileCandidates(cwd = process.cwd()): string[] {
  return [...new Set([path.resolve(cwd, ".env"), path.join(configDirectory(), ".env")])];
}

// Loads each existing candidate. Variables already in the environment win,
// since process.loadEnvFile never overwrites them. Returns the files read.
export function loadEnvFiles(cwd = process.cwd()): string[] {
  const loaded: string[] = [];
  for (const candidate of envFileCandidates(cwd)) {
    if (!existsSync(candidate)) continue;
    process.loadEnvFile(candidate);
    loaded.push(candidate);
  }
  return loaded;
}
