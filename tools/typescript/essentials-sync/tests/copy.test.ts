import { afterEach, describe, expect, it } from "vitest";
import { promises as fs } from "node:fs";
import path from "node:path";
import os from "node:os";
import { copyTreeVerbatim } from "../src/copy.js";

const tempRoots: string[] = [];

async function makeTree(
  files: Record<string, string>,
): Promise<string> {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "copy-test-"));
  tempRoots.push(root);
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

describe("copyTreeVerbatim", () => {
  it("copies files byte-for-byte", async () => {
    const source = await makeTree({
      "SKILL.md": "# Skill\nbody\n",
      "references/guide.md": "guidance\n",
    });
    const target = await makeTree({});

    const result = await copyTreeVerbatim(source, target);

    expect(result.filesCopied.sort()).toEqual(["SKILL.md", "references/guide.md"]);
    expect(await fs.readFile(path.join(target, "SKILL.md"), "utf8")).toBe("# Skill\nbody\n");
    expect(await fs.readFile(path.join(target, "references/guide.md"), "utf8")).toBe("guidance\n");
  });

  it("preserves the executable bit on scripts", async () => {
    const source = await makeTree({ "scripts/run.sh": "#!/usr/bin/env bash\n" });
    await fs.chmod(path.join(source, "scripts/run.sh"), 0o755);
    const target = await makeTree({});

    await copyTreeVerbatim(source, target);

    const stat = await fs.stat(path.join(target, "scripts/run.sh"));
    expect(stat.mode & 0o111).not.toBe(0);
  });

  // The safety invariant behind the fast path: the scanners skip gitignored
  // paths, so copying them would ship unscanned content (.env, local creds).
  it("never copies gitignored files", async () => {
    const source = await makeTree({
      ".gitignore": ".env\nsecrets/\n",
      "SKILL.md": "# Skill\n",
      ".env": "API_KEY=sk_live_do_not_ship\n",
      "secrets/token.txt": "token\n",
    });
    const target = await makeTree({});

    const result = await copyTreeVerbatim(source, target);

    expect(result.filesCopied).toContain("SKILL.md");
    expect(result.filesCopied).not.toContain(".env");
    expect(result.filesCopied).not.toContain("secrets/token.txt");
    await expect(fs.stat(path.join(target, ".env"))).rejects.toThrow();
    await expect(fs.stat(path.join(target, "secrets/token.txt"))).rejects.toThrow();
  });

  it("skips cache and build directories", async () => {
    const source = await makeTree({
      "scripts/report.py": "print('hi')\n",
      "scripts/__pycache__/report.cpython-312.pyc": "bytecode\n",
      "node_modules/dep/index.js": "module.exports = 1\n",
    });
    const target = await makeTree({});

    const result = await copyTreeVerbatim(source, target);

    expect(result.filesCopied).toEqual(["scripts/report.py"]);
  });

  // Re-syncing must not clobber files that exist only in the open-source repo.
  it("leaves target-only files in place", async () => {
    const source = await makeTree({ "SKILL.md": "updated\n" });
    const target = await makeTree({
      "SKILL.md": "stale\n",
      LICENSE: "Apache-2.0 full text\n",
    });

    await copyTreeVerbatim(source, target);

    expect(await fs.readFile(path.join(target, "SKILL.md"), "utf8")).toBe("updated\n");
    expect(await fs.readFile(path.join(target, "LICENSE"), "utf8")).toBe("Apache-2.0 full text\n");
  });

  it("reports copied files the text scanners could not read", async () => {
    const source = await makeTree({
      "SKILL.md": "# Skill\n",
      "docs/diagram.png": "not really a png\n",
    });
    const target = await makeTree({});

    const result = await copyTreeVerbatim(source, target);

    expect(result.filesCopied).toContain("docs/diagram.png");
    expect(result.unscannedFiles).toEqual(["docs/diagram.png"]);
  });

  it("skips symlinks instead of dereferencing them", async () => {
    const source = await makeTree({ "SKILL.md": "# Skill\n" });
    await fs.symlink(path.join(source, "SKILL.md"), path.join(source, "alias.md"));
    const target = await makeTree({});

    const result = await copyTreeVerbatim(source, target);

    expect(result.filesCopied).toEqual(["SKILL.md"]);
    expect(result.symlinksSkipped).toEqual(["alias.md"]);
  });
});
