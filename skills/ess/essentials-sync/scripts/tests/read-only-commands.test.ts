import assert from "node:assert/strict";
import { promises as fs } from "node:fs";
import path from "node:path";
import { afterEach, describe, it } from "node:test";
import { findEssItemRoot } from "../src/ess-items.ts";
import { formatScanFinding, resolveScanRoots, runScanCommand } from "../src/scan-command.ts";
import { compareEssItems } from "../src/status-command.ts";
import { makeRepo, removeTempDirs } from "./temp-repos.ts";

afterEach(removeTempDirs);

describe("findEssItemRoot", () => {
  const cases: Array<[string, string | null]> = [
    ["packages/python/ess-auth/src/ess_auth/x.py", "packages/python/ess-auth"],
    ["skills/ess/ess-git-tidy/SKILL.md", "skills/ess/ess-git-tidy"],
    ["instructions/ess/ess-okf-docs.instructions.md", "instructions/ess/ess-okf-docs.instructions.md"],
    [".agents/skills/ess-git-tidy/SKILL.md", null],
    ["skills/ess/essentials-sync/scripts/src/ess-scan.ts", null],
    ["plans/ess-verbatim-sync.md", null],
    ["tools/python/langsmith-onboarding/README.md", null],
  ];
  for (const [relPath, expected] of cases) {
    it(`${relPath} -> ${expected}`, () => {
      assert.equal(findEssItemRoot(relPath), expected);
    });
  }
});

describe("scan", () => {
  const skipSecretScanners = ["--no-trufflehog", "--no-secretlint"];

  it("scans the whole ess-* item that contains a changed file", async () => {
    const repo = await makeRepo("read-only", {
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

    assert.deepEqual(roots, [
      path.join(repo, "instructions/ess/ess-rule.instructions.md"),
      path.join(repo, "notes/plain.md"),
      path.join(repo, "packages/python/ess-demo"),
    ]);
  });

  it("exits 1 on critical findings and 0 when clean", async (t) => {
    t.mock.method(console, "log", () => {});
    const repo = await makeRepo("read-only", {
      "packages/python/ess-clean/README.md": "Contact bob@corp.example.com\n",
      "packages/python/ess-dirty/README.md": "Contact bob@corp.internal.net\n",
    });

    assert.equal(await runScanCommand(["packages/python/ess-clean", ...skipSecretScanners], repo), 0);
    assert.equal(await runScanCommand(["packages/python/ess-dirty/README.md", ...skipSecretScanners], repo), 1);
  });

  it("loads extra jargon terms from the repo root", async (t) => {
    t.mock.method(console, "log", () => {});
    const repo = await makeRepo("read-only", {
      ".essentials-sync-jargon.json": JSON.stringify({ terms: ["widgetco"] }),
      "skills/ess/ess-demo/SKILL.md": "Ask the WidgetCo help desk.\n",
    });

    assert.equal(await runScanCommand(["skills/ess/ess-demo/SKILL.md", ...skipSecretScanners], repo), 1);
  });

  it("rejects unknown options and a missing path", async () => {
    await assert.rejects(runScanCommand(["--nope", "x"]), /Unknown option '--nope'/);
    await assert.rejects(runScanCommand([]), /at least one path/);
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

    assert.equal(line, "pkg/config.py:3 [critical] secretlint @secretlint/secretlint-rule-github");
  });
});

describe("status", () => {
  it("classifies every ess-* item in either repo", async () => {
    const source = await makeRepo("status-source", {
      ".gitignore": ".env\n",
      "skills/ess/ess-same/SKILL.md": "same\n",
      "skills/ess/ess-same/.env": "ignored in source\n",
      "skills/ess/ess-changed/SKILL.md": "new\n",
      "packages/python/ess-new/README.md": "new\n",
      "instructions/ess/ess-rule.instructions.md": "rule\n",
      ".agents/skills/ess-same/SKILL.md": "installed copy\n",
    });
    const target = await makeRepo("status-target", {
      "skills/ess/ess-same/SKILL.md": "same\n",
      "skills/ess/ess-same/LICENSE": "Apache-2.0\n",
      "skills/ess/ess-changed/SKILL.md": "old\n",
      "skills/ess/ess-changed/extra.md": "extra\n",
      "instructions/ess/ess-rule.instructions.md": "rule\n",
      "skills/ess/ess-legacy/SKILL.md": "legacy\n",
    });

    const statuses = await compareEssItems(source, target);

    assert.deepEqual(statuses, [
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
    const source = await makeRepo("status-source", { "skills/ess/ess-x/run.sh": "echo hi\n" });
    const target = await makeRepo("status-target", { "skills/ess/ess-x/run.sh": "echo hi\n" });
    await fs.chmod(path.join(source, "skills/ess/ess-x/run.sh"), 0o755);

    const [status] = await compareEssItems(source, target);

    assert.equal(status?.state, "differs");
  });
});
