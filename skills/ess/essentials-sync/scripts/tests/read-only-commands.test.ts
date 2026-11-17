import assert from "node:assert/strict";
import { promises as fs } from "node:fs";
import path from "node:path";
import { afterEach, describe, it } from "node:test";
import { findEssItemRoot, repoOwnedItemFiles } from "../src/ess-items.ts";
import { formatScanFinding, resolveScanRoots, runScanCommand } from "../src/scan-command.ts";
import { compareEssItems, runStatusCommand } from "../src/status-command.ts";
import { makeRepo, makeTempDir, removeTempDirs } from "./temp-repos.ts";

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
      "jargon.json": JSON.stringify(["widgetco"]),
      "packages/python/ess-clean/README.md": "Contact bob@corp.example.com\n",
      "packages/python/ess-dirty/README.md": "Contact bob@corp.internal.net\n",
    });

    assert.equal(await runScanCommand(["packages/python/ess-clean", ...skipSecretScanners], repo), 0);
    assert.equal(await runScanCommand(["packages/python/ess-dirty/README.md", ...skipSecretScanners], repo), 1);
  });

  it("loads jargon terms from the repo root", async (t) => {
    t.mock.method(console, "log", () => {});
    const repo = await makeRepo("read-only", {
      "jargon.json": JSON.stringify({ terms: ["widgetco"] }),
      "skills/ess/ess-demo/SKILL.md": "Ask the WidgetCo help desk.\n",
    });

    assert.equal(await runScanCommand(["skills/ess/ess-demo/SKILL.md", ...skipSecretScanners], repo), 1);
  });

  it("loads an item's jargon file and never flags the file itself", async (t) => {
    t.mock.method(console, "log", () => {});
    const repo = await makeRepo("read-only", {
      "skills/ess/ess-clean/jargon.json": JSON.stringify(["widgetco"]),
      "skills/ess/ess-clean/SKILL.md": "# Clean\n",
      "skills/ess/ess-dirty/jargon.json": JSON.stringify(["widgetco"]),
      "skills/ess/ess-dirty/SKILL.md": "Ask the WidgetCo help desk.\n",
    });

    assert.equal(await runScanCommand(["skills/ess/ess-clean", ...skipSecretScanners], repo), 0);
    assert.equal(await runScanCommand(["skills/ess/ess-dirty", ...skipSecretScanners], repo), 1);
  });

  it("fails closed when no jargon file lists any terms", async () => {
    const repo = await makeRepo("read-only", {
      "jargon.json": JSON.stringify({ terms: [] }),
      "skills/ess/ess-demo/SKILL.md": "# Demo\n",
    });

    await assert.rejects(
      runScanCommand(["skills/ess/ess-demo", ...skipSecretScanners], repo),
      /No jargon terms found\. Looked for jargon\.json at: .*jargon\.json/,
    );
  });

  it("reads the jargon file named by --jargon-file", async (t) => {
    t.mock.method(console, "log", () => {});
    const repo = await makeRepo("read-only", {
      "company-jargon.json": JSON.stringify(["widgetco"]),
      "skills/ess/ess-demo/SKILL.md": "Ask the WidgetCo help desk.\n",
    });
    const args = ["skills/ess/ess-demo", ...skipSecretScanners];

    assert.equal(await runScanCommand(["--jargon-file", "company-jargon.json", ...args], repo), 1);
    await assert.rejects(runScanCommand(args, repo), /Looked for jargon\.json/);
  });

  it("rejects a malformed jargon file instead of scanning without it", async () => {
    const repo = await makeRepo("read-only", {
      "jargon.json": "[\"widgetco\",",
      "skills/ess/ess-demo/SKILL.md": "# Demo\n",
    });

    await assert.rejects(
      runScanCommand(["skills/ess/ess-demo", ...skipSecretScanners], repo),
      /jargon\.json is not valid JSON/,
    );
  });

  it("rejects unknown options, a missing path, and a --jargon-file path", async () => {
    await assert.rejects(runScanCommand(["--nope", "x"]), /Unknown option '--nope'/);
    await assert.rejects(runScanCommand([]), /at least one path/);
    await assert.rejects(runScanCommand(["--jargon-file", "config/jargon.json", "x"]), /file name, not a path/);
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

  it("never compares an item's jargon file, under any name", async () => {
    const source = await makeRepo("status-source", {
      "skills/ess/ess-x/SKILL.md": "same\n",
      "skills/ess/ess-x/jargon.json": '["acme-internal"]\n',
      "skills/ess/ess-y/SKILL.md": "same\n",
      "skills/ess/ess-y/company-jargon.json": '["acme-internal"]\n',
    });
    const target = await makeRepo("status-target", {
      "skills/ess/ess-x/SKILL.md": "same\n",
      "skills/ess/ess-y/SKILL.md": "same\n",
    });

    const statuses = await compareEssItems(source, target, repoOwnedItemFiles("company-jargon.json"));

    assert.deepEqual(statuses.map((status) => status.state), ["differs", "identical"]);
    assert.deepEqual(statuses[0]?.files, [{ path: "jargon.json", state: "only in source" }]);
    assert.deepEqual(
      (await compareEssItems(source, target)).map((status) => status.state),
      ["identical", "differs"],
    );
  });

  it("defaults the target to the current repo", async (t) => {
    const lines: string[] = [];
    t.mock.method(console, "log", (line: string) => lines.push(line));
    const source = await makeRepo("status-source", { "skills/ess/ess-x/SKILL.md": "same\n" });
    const target = await makeRepo("status-target", { "skills/ess/ess-x/SKILL.md": "same\n" });

    assert.equal(await runStatusCommand(["--source-repo", source], path.join(target, "skills")), 0);
    assert.match(lines.join("\n"), /identical\s+skills\/ess\/ess-x/);
  });

  it("refuses to compare a repo with itself", async () => {
    const repo = await makeRepo("status-same", { "skills/ess/ess-x/SKILL.md": "same\n" });

    await assert.rejects(runStatusCommand(["--source-repo", repo], repo), /same repo/);
    await assert.rejects(
      runStatusCommand(["--source-repo", path.join(repo, "skills", ".."), "--target-repo", repo], repo),
      /same repo/,
    );
  });

  it("needs --target-repo outside a git repo", async () => {
    const source = await makeRepo("status-source");
    const outside = await makeTempDir("status-outside");

    await assert.rejects(runStatusCommand(["--source-repo", source], outside), /no default target/);
  });
});
