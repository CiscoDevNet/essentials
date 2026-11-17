import { execFileSync } from "node:child_process";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

export type FileTree = Record<string, string>;

export const FIXTURES_DIRECTORY = fileURLToPath(new URL("./fixtures/", import.meta.url));

const tempRoots: string[] = [];

export async function makeTempDir(prefix: string): Promise<string> {
  // realpath: git reports /private/var/... for macOS temp dirs under /var.
  const root = await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), `${prefix}-`)));
  tempRoots.push(root);
  return root;
}

export async function writeTree(root: string, files: FileTree): Promise<void> {
  for (const [relPath, contents] of Object.entries(files)) {
    const abs = path.join(root, relPath);
    await fs.mkdir(path.dirname(abs), { recursive: true });
    await fs.writeFile(abs, contents, "utf8");
  }
}

// A temp directory that is a git work tree, which the file listing requires.
export async function makeRepo(prefix: string, files: FileTree = {}): Promise<string> {
  const root = await makeTempDir(prefix);
  git(root, "init", "--quiet");
  await writeTree(root, files);
  return root;
}

// A copy of tests/fixtures/<name> in its own temp repo, so the fixture tests
// run the same wherever the skill is installed.
export async function makeFixtureRepo(name: string): Promise<string> {
  const root = await makeRepo(`fixture-${name}`);
  await fs.cp(path.join(FIXTURES_DIRECTORY, name), root, { recursive: true });
  return root;
}

export function git(cwd: string, ...args: string[]): string {
  return execFileSync("git", args, { cwd, encoding: "utf8" });
}

export async function removeTempDirs(): Promise<void> {
  while (tempRoots.length > 0) {
    const root = tempRoots.pop();
    if (root) await fs.rm(root, { recursive: true, force: true });
  }
}
