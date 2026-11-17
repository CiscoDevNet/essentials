import assert from "node:assert/strict";
import { promises as fs } from "node:fs";
import path from "node:path";
import { afterEach, describe, it } from "node:test";
import { copyTreeVerbatim } from "../src/copy.ts";
import { listPublishableFiles } from "../src/file-set.ts";
import { scanPii } from "../src/scanners/pii.ts";
import { git, makeRepo, makeTempDir, removeTempDirs, writeTree } from "./temp-repos.ts";

afterEach(removeTempDirs);

describe("listPublishableFiles", () => {
  // A directory walk sees only .gitignore files at or below the directory, so
  // a rule in the repo root would be invisible when the package is scanned.
  it("honors .gitignore rules from the repo root", async () => {
    const repo = await makeRepo("file-set", {
      ".gitignore": ".env\n",
      "pkg/README.md": "# Package\n",
      "pkg/.env": "OWNER=jdoe@corp.internal.net\n",
    });

    assert.deepEqual(await listPublishableFiles(path.join(repo, "pkg")), ["README.md"]);
  });

  it("keeps tracked and untracked files that are not ignored", async () => {
    const repo = await makeRepo("file-set", { "pkg/tracked.md": "a\n", "pkg/new.md": "b\n" });
    git(repo, "add", "pkg/tracked.md");

    assert.deepEqual(await listPublishableFiles(path.join(repo, "pkg")), ["new.md", "tracked.md"]);
  });

  it("drops working notes and cache directories", async () => {
    const repo = await makeRepo("file-set", {
      "pkg/SKILL.md": "# Skill\n",
      "pkg/tmp-RECOMMENDATIONS.md": "notes\n",
      "pkg/scripts/__pycache__/x.pyc": "bytecode\n",
    });

    assert.deepEqual(await listPublishableFiles(path.join(repo, "pkg")), ["SKILL.md"]);
  });

  it("lists a single publishable file as the empty path", async () => {
    const repo = await makeRepo("file-set", {
      ".gitignore": "secret.md\n",
      "rule.md": "# Rule\n",
      "secret.md": "# Secret\n",
    });

    assert.deepEqual(await listPublishableFiles(path.join(repo, "rule.md")), [""]);
    assert.deepEqual(await listPublishableFiles(path.join(repo, "secret.md")), []);
  });

  it("refuses a directory outside a git work tree", async () => {
    const plain = await makeTempDir("file-set-plain");
    await writeTree(plain, { "README.md": "# Plain\n" });

    await assert.rejects(listPublishableFiles(plain), /not inside a git work tree/);
  });

  it("does not scan or copy a file ignored only by the repo root", async () => {
    const repo = await makeRepo("file-set", {
      ".gitignore": ".env\n",
      "pkg/README.md": "# Package\n",
      "pkg/.env": "OWNER=jdoe@corp.internal.net\n",
    });
    const pkg = path.join(repo, "pkg");
    const target = await makeRepo("file-set-target");

    assert.deepEqual(await scanPii(pkg, { severity: "critical" }), []);
    const result = await copyTreeVerbatim(pkg, target);

    assert.deepEqual(result.filesCopied, ["README.md"]);
    await assert.rejects(fs.stat(path.join(target, ".env")));
  });
});
