import assert from "node:assert/strict";
import { promises as fs } from "node:fs";
import path from "node:path";
import { afterEach, describe, it } from "node:test";
import { copyTreeVerbatim } from "../src/copy.ts";
import { makeRepo, makeTempDir, removeTempDirs, writeTree } from "./temp-repos.ts";

afterEach(removeTempDirs);

describe("copyTreeVerbatim", () => {
  it("leaves the item's own LICENSE to each repo", async () => {
    const source = await makeRepo("copy-source", {
      "SKILL.md": "# Skill\n",
      LICENSE: "source license\n",
      "vendor/LICENSE": "vendored license\n",
    });
    const target = await makeRepo("copy-target", { LICENSE: "target license\n" });

    const result = await copyTreeVerbatim(source, target);

    assert.deepEqual(result.filesCopied.sort(), ["SKILL.md", "vendor/LICENSE"]);
    assert.equal(await fs.readFile(path.join(target, "LICENSE"), "utf8"), "target license\n");
  });

  it("copies files byte-for-byte", async () => {
    const source = await makeRepo("copy-source", {
      "SKILL.md": "# Skill\nbody\n",
      "references/guide.md": "guidance\n",
    });
    const target = await makeRepo("copy-target");

    const result = await copyTreeVerbatim(source, target);

    assert.deepEqual(result.filesCopied.sort(), ["SKILL.md", "references/guide.md"]);
    assert.equal(await fs.readFile(path.join(target, "SKILL.md"), "utf8"), "# Skill\nbody\n");
    assert.equal(await fs.readFile(path.join(target, "references/guide.md"), "utf8"), "guidance\n");
  });

  it("preserves the executable bit on scripts", async () => {
    const source = await makeRepo("copy-source", { "scripts/run.sh": "#!/usr/bin/env bash\n" });
    await fs.chmod(path.join(source, "scripts/run.sh"), 0o755);
    const target = await makeRepo("copy-target");

    await copyTreeVerbatim(source, target);

    const stat = await fs.stat(path.join(target, "scripts/run.sh"));
    assert.notEqual(stat.mode & 0o111, 0);
  });

  // The safety invariant behind the fast path: the scanners skip gitignored
  // paths, so copying them would ship unscanned content (.env, local creds).
  it("never copies gitignored files", async () => {
    const source = await makeRepo("copy-source", {
      ".gitignore": ".env\nsecrets/\n",
      "SKILL.md": "# Skill\n",
      ".env": "API_KEY=sk_live_do_not_ship\n",
      "secrets/token.txt": "token\n",
    });
    const target = await makeRepo("copy-target");

    const result = await copyTreeVerbatim(source, target);

    assert.ok(result.filesCopied.includes("SKILL.md"));
    assert.ok(!result.filesCopied.includes(".env"));
    assert.ok(!result.filesCopied.includes("secrets/token.txt"));
    await assert.rejects(fs.stat(path.join(target, ".env")));
    await assert.rejects(fs.stat(path.join(target, "secrets/token.txt")));
  });

  it("skips cache and build directories", async () => {
    const source = await makeRepo("copy-source", {
      "scripts/report.py": "print('hi')\n",
      "scripts/__pycache__/report.cpython-312.pyc": "bytecode\n",
      "node_modules/dep/index.js": "module.exports = 1\n",
    });
    const target = await makeRepo("copy-target");

    const result = await copyTreeVerbatim(source, target);

    assert.deepEqual(result.filesCopied, ["scripts/report.py"]);
  });

  // Re-syncing must not clobber files that exist only in the target repo.
  it("leaves target-only files in place", async () => {
    const source = await makeRepo("copy-source", { "SKILL.md": "updated\n" });
    const target = await makeRepo("copy-target", {
      "SKILL.md": "stale\n",
      LICENSE: "Apache-2.0 full text\n",
    });

    await copyTreeVerbatim(source, target);

    assert.equal(await fs.readFile(path.join(target, "SKILL.md"), "utf8"), "updated\n");
    assert.equal(await fs.readFile(path.join(target, "LICENSE"), "utf8"), "Apache-2.0 full text\n");
  });

  it("reports copied files the text scanners could not read", async () => {
    const source = await makeRepo("copy-source", {
      "SKILL.md": "# Skill\n",
      "docs/diagram.png": "not really a png\n",
    });
    const target = await makeRepo("copy-target");

    const result = await copyTreeVerbatim(source, target);

    assert.ok(result.filesCopied.includes("docs/diagram.png"));
    assert.deepEqual(result.unscannedFiles, ["docs/diagram.png"]);
  });

  it("skips symlinks instead of dereferencing them", async () => {
    const source = await makeRepo("copy-source", { "SKILL.md": "# Skill\n" });
    await fs.symlink(path.join(source, "SKILL.md"), path.join(source, "alias.md"));
    const target = await makeRepo("copy-target");

    const result = await copyTreeVerbatim(source, target);

    assert.deepEqual(result.filesCopied, ["SKILL.md"]);
    assert.deepEqual(result.symlinksSkipped, ["alias.md"]);
  });

  it("refuses a source outside a git work tree", async () => {
    const source = await makeTempDir("copy-plain");
    await writeTree(source, { "SKILL.md": "# Skill\n" });
    const target = await makeRepo("copy-target");

    await assert.rejects(copyTreeVerbatim(source, target), /not inside a git work tree/);
  });
});
