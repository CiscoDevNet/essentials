import { afterEach, describe, expect, it } from "vitest";
import { promises as fs } from "node:fs";
import path from "node:path";
import os from "node:os";
import { execa } from "execa";
import { listPublishableFiles } from "../src/file-set.js";
import { copyTreeVerbatim } from "../src/copy.js";
import { scanPii } from "../src/scanners/pii.js";

const tempRoots: string[] = [];

async function makeRepo(files: Record<string, string>): Promise<string> {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "file-set-test-"));
  tempRoots.push(root);
  await execa("git", ["init", "--quiet"], { cwd: root });
  for (const [relPath, contents] of Object.entries(files)) {
    const abs = path.join(root, relPath);
    await fs.mkdir(path.dirname(abs), { recursive: true });
    await fs.writeFile(abs, contents, "utf8");
  }
  return root;
}

afterEach(async () => {
  while (tempRoots.length > 0) {
    const root = tempRoots.pop();
    if (root) await fs.rm(root, { recursive: true, force: true });
  }
});

describe("listPublishableFiles", () => {
  // globby reads .gitignore files at or below its cwd only, so a rule in the
  // repo root used to be invisible when the package directory was scanned.
  it("honors .gitignore rules from the repo root", async () => {
    const repo = await makeRepo({
      ".gitignore": ".env\n",
      "pkg/README.md": "# Package\n",
      "pkg/.env": "OWNER=jdoe@corp.internal.net\n",
    });

    const files = await listPublishableFiles(path.join(repo, "pkg"));

    expect(files).toEqual(["README.md"]);
  });

  it("keeps tracked and untracked files that are not ignored", async () => {
    const repo = await makeRepo({ "pkg/tracked.md": "a\n", "pkg/new.md": "b\n" });
    await execa("git", ["add", "pkg/tracked.md"], { cwd: repo });

    const files = await listPublishableFiles(path.join(repo, "pkg"));

    expect(files).toEqual(["new.md", "tracked.md"]);
  });

  it("drops working notes and cache directories", async () => {
    const repo = await makeRepo({
      "pkg/SKILL.md": "# Skill\n",
      "pkg/tmp-RECOMMENDATIONS.md": "notes\n",
      "pkg/scripts/__pycache__/x.pyc": "bytecode\n",
    });

    const files = await listPublishableFiles(path.join(repo, "pkg"));

    expect(files).toEqual(["SKILL.md"]);
  });

  it("does not scan or copy a file ignored only by the repo root", async () => {
    const repo = await makeRepo({
      ".gitignore": ".env\n",
      "pkg/README.md": "# Package\n",
      "pkg/.env": "OWNER=jdoe@corp.internal.net\n",
    });
    const pkg = path.join(repo, "pkg");
    const target = await fs.mkdtemp(path.join(os.tmpdir(), "file-set-target-"));
    tempRoots.push(target);

    expect(await scanPii(pkg, { severity: "critical" })).toEqual([]);
    const result = await copyTreeVerbatim(pkg, target);

    expect(result.filesCopied).toEqual(["README.md"]);
    await expect(fs.stat(path.join(target, ".env"))).rejects.toThrow();
  });
});
