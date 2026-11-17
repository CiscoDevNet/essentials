import { promises as fs } from "node:fs";
import path from "node:path";
import { UsageError } from "./args.ts";
import { findGitRoot } from "./ess-items.ts";

// The target is the repo the command runs in, unless --target-repo names
// another one.
export async function resolveTargetRepo(given: string | undefined, cwd = process.cwd()): Promise<string> {
  if (given) return path.resolve(cwd, given);
  const root = await findGitRoot(cwd);
  if (!root) {
    throw new UsageError(
      `${cwd} is not inside a git repo, so there is no default target. `
        + "Run from the target repo, or pass --target-repo.",
    );
  }
  return root;
}

// The repo containing sourceAbs: --source-repo when given, else the git root
// above it. sourceAbs must exist and lie inside the repo.
export async function resolveSourceRepo(sourceAbs: string, given?: string): Promise<string> {
  let stat;
  try {
    stat = await fs.stat(sourceAbs);
  } catch {
    throw new Error(`--source does not exist: ${sourceAbs}`);
  }
  const repo = given
    ? path.resolve(given)
    : await findGitRoot(stat.isFile() ? path.dirname(sourceAbs) : sourceAbs);
  if (!repo) {
    throw new Error(`--source is not inside a git repo: ${sourceAbs}. Pass --source-repo.`);
  }
  if (repoRelativePath(await canonicalPath(repo), await canonicalPath(sourceAbs)) === null) {
    throw new Error(`--source (${sourceAbs}) is not inside --source-repo (${repo})`);
  }
  return repo;
}

// Where the item sits in its repo, so the target can mirror it. Null when the
// item is the repo itself.
export async function mirrorPath(sourceRepo: string, sourceAbs: string): Promise<string | null> {
  const relative = repoRelativePath(await canonicalPath(sourceRepo), await canonicalPath(sourceAbs));
  return relative ? relative : null;
}

export async function assertDifferentRepos(sourceRepo: string, targetRepo: string): Promise<void> {
  if ((await canonicalPath(sourceRepo)) === (await canonicalPath(targetRepo))) {
    throw new UsageError(
      `The source and target are the same repo (${targetRepo}). Run from the target repo, `
        + "or pass --target-repo.",
    );
  }
}

function repoRelativePath(repo: string, target: string): string | null {
  const relative = path.relative(repo, target);
  if (relative.startsWith("..") || path.isAbsolute(relative)) return null;
  return relative;
}

// macOS reaches /tmp through a symlink, so compare real paths.
async function canonicalPath(target: string): Promise<string> {
  try {
    return await fs.realpath(target);
  } catch {
    return path.resolve(target);
  }
}
