import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { copyTreeVerbatim } from "./copy.ts";
import { run } from "./exec.ts";
import { PROGRAM_NAME } from "./program.ts";

// Root files an extract run may edit besides the tool itself: it registers
// the new package as a workspace member.
const SOURCE_ROOT_FILES = ["pyproject.toml"];

// A fresh git repo in the temp directory for a dry run to write into. The
// scanners list files with git, so a plain directory would not do.
export async function createStagingRepo(label: string): Promise<string> {
  const root = await fs.realpath(
    await fs.mkdtemp(path.join(os.tmpdir(), `${PROGRAM_NAME}-dryrun-${label}-`)),
  );
  const result = await run("git", ["init", "--quiet"], { cwd: root });
  if (result.exitCode !== 0) {
    throw new Error(`git init failed in ${root}: ${result.stderr.trim()}`);
  }
  return root;
}

// Copies the publishable files of each repo-relative path that exists in
// fromRepo into the same place in toRepo. Used to seed a staging repo so a dry
// run sees what the real run would: the existing target item, or the tool an
// extract run rewrites.
export async function seedStagingRepo(
  fromRepo: string,
  toRepo: string,
  relPaths: readonly string[],
): Promise<void> {
  for (const relPath of relPaths) {
    const from = path.join(fromRepo, relPath);
    try {
      await fs.lstat(from);
    } catch {
      continue;
    }
    await copyTreeVerbatim(from, path.join(toRepo, relPath));
  }
}

// Extract mode writes into the source repo too (the new package, the
// rewritten wrapper, the workspace member list), so its dry run works on a
// staging copy of just those paths.
export async function stageExtractSource(
  sourceRepoRoot: string,
  relPaths: readonly string[],
): Promise<string> {
  const staged = await createStagingRepo("source");
  await seedStagingRepo(sourceRepoRoot, staged, [...SOURCE_ROOT_FILES, ...relPaths]);
  return staged;
}
