import { promises as fs } from "node:fs";
import path from "node:path";
import { run } from "./exec.ts";
import { PROGRAM_NAME } from "./program.ts";

// Always skipped, even when nothing ignores them. These are caches, build
// output, and VCS/dependency directories that never carry meaningful
// findings.
export const HARD_SKIP_DIRECTORIES = [
  "node_modules", ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
  ".ruff_cache", ".mypy_cache", "dist", "build", ".pulumi",
];

// Working notes for the operator. Target repos gitignore `tmp[-.]*`, so these
// are never published; skipping them keeps scanning and copying in lockstep.
const WORKING_NOTE_PATTERN = /^tmp[-.]/;

// Lists the files under rootAbs that would be published, as sorted paths
// relative to rootAbs.
//
// Scanners and the copier both read this list, so a clean scan covers exactly
// the files a copy ships. The list comes from `git ls-files`, which applies
// every ignore source git does: .gitignore files in ancestor directories,
// .git/info/exclude, and the global excludes file. rootAbs must therefore be
// inside a git work tree.
//
// rootAbs may also be a single file. The result is then [""] when the file is
// publishable and [] when it is not, so path.join(rootAbs, entry) still names
// the file.
export async function listPublishableFiles(rootAbs: string): Promise<string[]> {
  const stat = await fs.lstat(rootAbs);
  if (!stat.isDirectory()) {
    const name = path.basename(rootAbs);
    const listed = await listWithGit(path.dirname(rootAbs), name);
    return listed.includes(name) && !isSkipped(name) ? [""] : [];
  }

  const kept = (await listWithGit(rootAbs, ".")).filter((relPath) => !isSkipped(relPath));
  return [...new Set(kept)].sort();
}

function isSkipped(relPath: string): boolean {
  const parts = relPath.split("/");
  if (parts.some((part) => HARD_SKIP_DIRECTORIES.includes(part))) {
    return true;
  }
  return WORKING_NOTE_PATTERN.test(parts[parts.length - 1] ?? "");
}

async function listWithGit(rootAbs: string, pathspec: string): Promise<string[]> {
  const inside = await run("git", ["rev-parse", "--is-inside-work-tree"], { cwd: rootAbs });
  if (inside.exitCode !== 0 || inside.stdout.trim() !== "true") {
    throw new Error(
      `${rootAbs} is not inside a git work tree. ${PROGRAM_NAME} decides what would be `
        + "published from git's ignore rules, so it only reads files in a git repository.",
    );
  }

  // --cached keeps tracked files even when an ignore rule would match them;
  // --others --exclude-standard adds untracked files that are not ignored.
  // Paths come back relative to cwd, which is rootAbs.
  const listed = await run(
    "git",
    ["ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", `:(literal)${pathspec}`],
    { cwd: rootAbs },
  );
  if (listed.exitCode !== 0) {
    throw new Error(`git ls-files failed in ${rootAbs}: ${listed.stderr.trim()}`);
  }
  const relPaths = listed.stdout.split("\0").filter((entry) => entry !== "");

  // A tracked file deleted from the work tree is still in the index; it is
  // not on disk, so there is nothing to scan or copy.
  const present: string[] = [];
  for (const relPath of relPaths) {
    try {
      await fs.lstat(path.join(rootAbs, relPath));
      present.push(relPath);
    } catch {
      // Deleted in the work tree.
    }
  }
  return present;
}
