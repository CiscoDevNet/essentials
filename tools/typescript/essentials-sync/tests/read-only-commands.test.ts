import { afterEach, describe, expect, it, vi } from "vitest";
import { promises as fs } from "node:fs";
import path from "node:path";
import os from "node:os";
import { execa } from "execa";
import { findEssItemRoot } from "../src/ess-items.js";
import { formatScanFinding, resolveScanRoots, runScanCommand } from "../src/scan-command.js";
import { compareEssItems } from "../src/status-command.js";

const tempRoots: string[] = [];

async function makeRepo(files: Record<string, string>): Promise<string> {
  // realpath: git reports /private/var/... for macOS temp dirs under /var.
  const root = await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), "read-only-test-")));
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
  vi.restoreAllMocks();
  while (tempRoots.length > 0) {
    const root = tempRoots.pop();
    if (root) await fs.rm(root, { recursive: true, force: true });
  }
});

describe("findEssItemRoot", () => {
  it.each([
    ["packages/python/ess-auth/src/ess_auth/x.py", "packages/python/ess-auth"],
    ["skills/ess/ess-git-tidy/SKILL.md", "skills/ess/ess-git-tidy"],
    ["instructions/ess/ess-okf-docs.instructions.md", "instructions/ess/ess-okf-docs.instructions.md"],
    [".agents/skills/ess-git-tidy/SKILL.md", null],
    ["tools/typescript/essentials-sync/src/ess-scan.ts", null],
    ["plans/ess-verbatim-sync.md", null],
    ["tools/python/langsmith-onboarding/README.md", null],
  ])("%s -> %s", (relPath, expected) => {
    expect(findEssItemRoot(relPath)).toBe(expected);
  });
});

describe("scan", () => {
  it("scans the whole ess-* item that contains a changed file", async () => {
    const repo = await makeRepo({
      "packages/python/ess-demo/README.md": "# Demo\n",
      "packages/python/ess-demo/src/a.py": "x = 1\n",
      "instructions/ess/ess-rule.instructions.md": "# Rule\n",
      "notes/plain.md": "# Plain\n",
    });

    const roots = await resolveScanRoots(
      ["packages/python/ess-demo/src/a.py", "packages/python/ess-demo/README.md", "instructions/ess/ess-rule.instructions.md", "notes/plain.md"],
      repo,
      repo,
    );

    expect(roots).toEqual([
      path.join(repo, "instructions/ess/ess-rule.instructions.md"),
      path.join(repo, "notes/plain.md"),
      path.join(repo, "packages/python/ess-demo"),
    ]);
  });

  it("exits 1 on critical findings and 0 when clean", async () => {
    vi.spyOn(console, "log").mockImplementation(() => {});
    const repo = await makeRepo({
      "packages/python/ess-clean/README.md": "Contact bob@corp.example.com\n",
      "packages/python/ess-dirty/README.md": "Contact bob@corp.internal.net\n",
    });
    const skipSecretScanners = ["--no-trufflehog", "--no-secretlint"];

    expect(await runScanCommand(["packages/python/ess-clean", ...skipSecretScanners], repo)).toBe(0);
    expect(await runScanCommand(["packages/python/ess-dirty/README.md", ...skipSecretScanners], repo)).toBe(1);
  });

  it("loads extra jargon terms from the repo root", async () => {
    vi.spyOn(console, "log").mockImplementation(() => {});
    const repo = await makeRepo({
      ".essentials-sync-jargon.json": JSON.stringify({ terms: ["widgetco"] }),
      "skills/ess/ess-demo/SKILL.md": "Ask the WidgetCo help desk.\n",
    });

    expect(await runScanCommand(["skills/ess/ess-demo/SKILL.md", "--no-trufflehog", "--no-secretlint"], repo)).toBe(1);
  });

  it("prints only the rule for secret findings", () => {
    const line = formatScanFinding(
      {
        file: "/repo/pkg/config.py",
        line: 3,
        type: "secret",
        severity: "critical",
        source: "secretlint",
        message: "found token: ***",
        term: "@secretlint/secretlint-rule-github",
      },
      "/repo",
    );

    expect(line).toBe("pkg/config.py:3 [critical] secretlint @secretlint/secretlint-rule-github");
  });
});

describe("status", () => {
  it("classifies every ess-* item in either repo", async () => {
    const source = await makeRepo({
      ".gitignore": ".env\n",
      "skills/ess/ess-same/SKILL.md": "same\n",
      "skills/ess/ess-same/.env": "ignored in source\n",
      "skills/ess/ess-changed/SKILL.md": "new\n",
      "packages/python/ess-new/README.md": "new\n",
      "instructions/ess/ess-rule.instructions.md": "rule\n",
      ".agents/skills/ess-same/SKILL.md": "installed copy\n",
    });
    const target = await makeRepo({
      "skills/ess/ess-same/SKILL.md": "same\n",
      "skills/ess/ess-same/LICENSE": "Apache-2.0\n",
      "skills/ess/ess-changed/SKILL.md": "old\n",
      "skills/ess/ess-changed/extra.md": "extra\n",
      "instructions/ess/ess-rule.instructions.md": "rule\n",
      "skills/ess/ess-legacy/SKILL.md": "legacy\n",
    });

    const statuses = await compareEssItems(source, target);

    expect(statuses).toEqual([
      { item: "instructions/ess/ess-rule.instructions.md", state: "identical", files: [] },
      { item: "packages/python/ess-new", state: "only in source", files: [] },
      {
        item: "skills/ess/ess-changed",
        state: "differs",
        files: [
          { path: "SKILL.md", state: "changed" },
          { path: "extra.md", state: "only in target" },
        ],
      },
      { item: "skills/ess/ess-legacy", state: "only in target", files: [] },
      { item: "skills/ess/ess-same", state: "identical", files: [] },
    ]);
  });

  it("treats a lost executable bit as a change", async () => {
    const source = await makeRepo({ "skills/ess/ess-x/run.sh": "echo hi\n" });
    const target = await makeRepo({ "skills/ess/ess-x/run.sh": "echo hi\n" });
    await fs.chmod(path.join(source, "skills/ess/ess-x/run.sh"), 0o755);

    const [status] = await compareEssItems(source, target);

    expect(status?.state).toBe("differs");
  });
});
