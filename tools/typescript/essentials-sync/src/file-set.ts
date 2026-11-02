import { promises as fs } from "node:fs";
import path from "node:path";
import { execa } from "execa";
import { globby } from "globby";

// Always skipped, even when the scanned tree has no .gitignore. These are
// caches, build output, and VCS/dependency directories that never carry
// meaningful findings.
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
// the files a copy ships. Inside a git work tree the list comes from
// `git ls-files`, which applies every ignore source git does: .gitignore files
// in ancestor directories, .git/info/exclude, and the global excludes file.
// globby only reads .gitignore files at or below its cwd, so a package-level
// walk misses rules in the repo root and would ship a root-ignored `.env`.
// Outside a work tree (fixtures, scratch copies) globby is the fallback.
//
// rootAbs may also be a single file. The result is then [""] when the file is
// publishable and [] when it is not, so path.join(rootAbs, entry) still names
// the file.
export async function listPublishableFiles(rootAbs: string): Promise<string[]> {
  const stat = await fs.lstat(rootAbs);
  if (!stat.isDirectory()) {
    const name = path.basename(rootAbs);
    const listed = (await listWithGit(path.dirname(rootAbs), name)) ?? [name];
    return listed.includes(name) && !isSkipped(name) ? [""] : [];
  }

  const fromGit = await listWithGit(rootAbs, ".");
  const candidates = fromGit ?? (await listWithGlobby(rootAbs));
  const kept = candidates.filter((relPath) => !isSkipped(relPath));
  return [...new Set(kept)].sort();
}

function isSkipped(relPath: string): boolean {
  const parts = relPath.split("/");
  if (parts.some((part) => HARD_SKIP_DIRECTORIES.includes(part))) {
    return true;
  }
  return WORKING_NOTE_PATTERN.test(parts[parts.length - 1] ?? "");
}

async function listWithGit(rootAbs: string, pathspec: string): Promise<string[] | null> {
  const inside = await execa("git", ["rev-parse", "--is-inside-work-tree"], {
    cwd: rootAbs,
    reject: false,
  });
  if (inside.exitCode !== 0 || inside.stdout.trim() !== "true") {
    return null;
  }

  // --cached keeps tracked files even when an ignore rule would match them;
  // --others --exclude-standard adds untracked files that are not ignored.
  // Paths come back relative to cwd, which is rootAbs.
  const listed = await execa(
    "git",
    ["ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", `:(literal)${pathspec}`],
    { cwd: rootAbs },
  );
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

async function listWithGlobby(rootAbs: string): Promise<string[]> {
  // onlyFiles is off so symlinks come back as entries the copier can classify
  // and report; globby would otherwise drop them silently.
  const entries = await globby("**/*", {
    cwd: rootAbs,
    dot: true,
    gitignore: true,
    onlyFiles: false,
    followSymbolicLinks: false,
    ignore: HARD_SKIP_DIRECTORIES.map((dir) => `**/${dir}/**`),
  });
  const files: string[] = [];
  for (const relPath of entries) {
    const stat = await fs.lstat(path.join(rootAbs, relPath));
    if (!stat.isDirectory()) {
      files.push(relPath);
    }
  }
  return files;
}
