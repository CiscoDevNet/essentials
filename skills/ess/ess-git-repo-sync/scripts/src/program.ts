import os from "node:os";
import path from "node:path";

export const PROGRAM_NAME = "ess-git-repo-sync";

export const MIN_NODE_MAJOR = 24;

// ${XDG_CONFIG_HOME}/<program>, or ~/.config/<program>. XDG variables count
// only when they are absolute paths.
export function configDirectory(): string {
  return path.join(xdgBase("XDG_CONFIG_HOME", ".config"), PROGRAM_NAME);
}

// ${XDG_CACHE_HOME}/<program>, or ~/.cache/<program>.
export function cacheDirectory(): string {
  return path.join(xdgBase("XDG_CACHE_HOME", ".cache"), PROGRAM_NAME);
}

function xdgBase(variable: string, fallback: string): string {
  const value = process.env[variable];
  return value && path.isAbsolute(value) ? value : path.join(os.homedir(), fallback);
}
