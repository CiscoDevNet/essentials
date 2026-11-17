import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";
import { afterEach, describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import { UsageError } from "../src/args.ts";
import { confirmWrite } from "../src/confirm.ts";
import { loadEnvFiles } from "../src/env.ts";
import { buildSyncPlan, parseSyncArgs, stageDryRunPlan } from "../src/sync-command.ts";
import { git, makeRepo, makeTempDir, removeTempDirs, writeTree } from "./temp-repos.ts";

const CLI = fileURLToPath(new URL("../src/cli.ts", import.meta.url));

const stagingRepos: string[] = [];

afterEach(async () => {
  await removeTempDirs();
  while (stagingRepos.length > 0) {
    const repo = stagingRepos.pop();
    if (repo) await fs.rm(repo, { recursive: true, force: true });
  }
});

const neverAsk = (): Promise<string> => {
  throw new Error("prompted");
};

describe("confirmWrite", () => {
  it("lets --dry-run win over --yes, without prompting", async () => {
    const outcome = await confirmWrite({ dryRun: true, yes: true, isInteractive: true, question: "Write?", ask: neverAsk });
    assert.equal(outcome, "dry-run");
  });

  it("skips the prompt with --yes", async () => {
    const outcome = await confirmWrite({ dryRun: false, yes: true, isInteractive: false, question: "Write?", ask: neverAsk });
    assert.equal(outcome, "confirmed");
  });

  it("refuses a real write with no terminal and no --yes", async () => {
    const outcome = await confirmWrite({ dryRun: false, yes: false, isInteractive: false, question: "Write?", ask: neverAsk });
    assert.equal(outcome, "needs-yes");
  });

  it("writes only on an explicit yes", async () => {
    const ask = (answer: string) => () => Promise.resolve(answer);
    const base = { dryRun: false, yes: false, isInteractive: true, question: "Write?" };
    assert.equal(await confirmWrite({ ...base, ask: ask("y") }), "confirmed");
    assert.equal(await confirmWrite({ ...base, ask: ask(" YES ") }), "confirmed");
    assert.equal(await confirmWrite({ ...base, ask: ask("") }), "declined");
    assert.equal(await confirmWrite({ ...base, ask: ask("sure") }), "declined");
  });
});

describe("parseSyncArgs", () => {
  it("keeps --dry-run and --yes independent", () => {
    const options = parseSyncArgs(["--source", "/s", "--target-repo", "/t", "--dry-run", "--yes"]);
    assert.equal(options?.dryRun, true);
    assert.equal(options?.yes, true);
  });

  it("accepts the negated booleans", () => {
    const options = parseSyncArgs([
      "-s", "/s", "-r", "/t", "-t", "x",
      "--no-extract", "--no-fast-copy", "--no-source-scan", "--no-adversarial-review",
    ]);
    assert.deepEqual(
      [options?.extract, options?.fastCopy, options?.sourceScan, options?.adversarialReview],
      [false, false, false, false],
    );
  });

  it("leaves the target repo and path to be resolved later", () => {
    const options = parseSyncArgs(["-s", "/s", "--no-extract"]);
    assert.equal(options?.targetRepo, undefined);
    assert.equal(options?.targetPath, undefined);
    assert.equal(options?.jargonFile, "jargon.json");
  });

  it("rejects bad input as usage errors", () => {
    assert.throws(() => parseSyncArgs(["--target-repo", "/t"]), UsageError);
    assert.throws(() => parseSyncArgs(["-s", "/s", "--max-revisions", "two"]), /non-negative integer/);
    assert.throws(() => parseSyncArgs(["-s", "/s", "--apply"]), UsageError);
    assert.throws(() => parseSyncArgs(["-s", "/s", "--jargon-file", "../jargon.json"]), /file name, not a path/);
  });

  it("returns null for --help", () => {
    assert.equal(parseSyncArgs(["--help"]), null);
  });
});

describe("buildSyncPlan", () => {
  const plan = async (argv: string[]) => {
    const options = parseSyncArgs(argv);
    assert.ok(options);
    assert.ok(options.targetRepo);
    return (await buildSyncPlan(options, { source: options.source, targetRepo: options.targetRepo })).plan;
  };

  it("mirrors where the item sits in the source repo", async () => {
    const source = await makeRepo("plan-source", {
      "skills/ess/ess-demo/SKILL.md": "# Demo\n",
      "instructions/ess/ess-rule.instructions.md": "# Rule\n",
    });
    const target = await makeRepo("plan-target");

    const directory = await plan(["-s", path.join(source, "skills/ess/ess-demo"), "-r", target, "--no-extract"]);
    const file = await plan([
      "-s", path.join(source, "instructions/ess/ess-rule.instructions.md"), "-r", target, "--no-extract",
    ]);

    assert.equal(directory.targetPathRel, "skills/ess/ess-demo");
    assert.equal(directory.sourceRepoRoot, source);
    assert.equal(file.targetPathRel, "instructions/ess/ess-rule.instructions.md");
    assert.equal(file.targetAbs, path.join(target, "instructions/ess/ess-rule.instructions.md"));
  });

  it("lets --target-path override the mirrored path", async () => {
    const source = await makeRepo("plan-source", { "skills/ess/ess-demo/SKILL.md": "# Demo\n" });
    const target = await makeRepo("plan-target");

    const result = await plan([
      "-s", path.join(source, "skills/ess/ess-demo"), "-r", target, "-t", "skills/ess-demo", "--no-extract",
    ]);

    assert.equal(result.targetPathRel, "skills/ess-demo");
  });

  it("refuses a target that is the source repo", async () => {
    const repo = await makeRepo("plan-same", { "skills/ess/ess-demo/SKILL.md": "# Demo\n" });

    await assert.rejects(
      plan(["-s", path.join(repo, "skills/ess/ess-demo"), "-r", path.join(repo, "skills", ".."), "--no-extract"]),
      /same repo/,
    );
  });

  it("refuses a source outside a git repo, and a source that is a whole repo", async () => {
    const outside = await makeTempDir("plan-outside");
    await writeTree(outside, { "SKILL.md": "# Demo\n" });
    const source = await makeRepo("plan-source", { "SKILL.md": "# Demo\n" });
    const target = await makeRepo("plan-target");

    await assert.rejects(plan(["-s", outside, "-r", target, "--no-extract"]), /not inside a git repo/);
    await assert.rejects(plan(["-s", source, "-r", target, "--no-extract"]), /pass --target-path/);
  });
});

describe("sync from the command line", () => {
  const runSync = (cwd: string, config: string, args: string[]) =>
    spawnSync(process.execPath, [CLI, "sync", ...args], {
      cwd,
      input: "",
      encoding: "utf8",
      env: { ...process.env, CURSOR_API_KEY: "test-key", XDG_CONFIG_HOME: config },
    });

  it("exits 1 before writing when there is no terminal and no --yes", async () => {
    const source = await makeRepo("gate-source", { "skills/ess/ess-demo/SKILL.md": "# Demo\n" });
    const target = await makeRepo("gate-target");
    const config = await makeTempDir("gate-config");

    const result = runSync(config, config, [
      "--source", path.join(source, "skills/ess/ess-demo"), "--target-repo", target, "--no-extract",
    ]);

    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stderr, /--yes/);
    assert.deepEqual(await fs.readdir(target), [".git"]);
  });

  it("defaults the target to the repo it runs in", async () => {
    const source = await makeRepo("gate-source", { "skills/ess/ess-demo/SKILL.md": "# Demo\n" });
    const target = await makeRepo("gate-target", { "docs/README.md": "# Docs\n" });
    const config = await makeTempDir("gate-config");

    const result = runSync(path.join(target, "docs"), config, [
      "--source", path.join(source, "skills/ess/ess-demo"), "--no-extract",
    ]);

    assert.equal(result.status, 1, result.stderr);
    assert.ok(result.stdout.includes(`target repo=${target}`), result.stdout);
    assert.ok(result.stdout.includes(`target=${path.join(target, "skills/ess/ess-demo")}`), result.stdout);
  });

  it("exits 1 when no jargon file lists any terms, even on a dry run", async () => {
    const source = await makeRepo("gate-source", {
      "jargon.json": JSON.stringify({ terms: [] }),
      "skills/ess/ess-demo/SKILL.md": "# Demo\n",
    });
    const target = await makeRepo("gate-target");
    const config = await makeTempDir("gate-config");

    const result = runSync(target, config, [
      "--source", path.join(source, "skills/ess/ess-demo"), "--no-extract", "--dry-run",
    ]);

    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stderr, /No jargon terms found\. Looked for jargon\.json at:/);
    assert.ok(result.stderr.includes(path.join(source, "jargon.json")), result.stderr);
    assert.ok(result.stderr.includes(path.join(target, "jargon.json")), result.stderr);
  });

  it("looks for the file named by --jargon-file", async () => {
    const source = await makeRepo("gate-source", {
      "jargon.json": JSON.stringify(["acme-internal"]),
      "skills/ess/ess-demo/SKILL.md": "# Demo\n",
    });
    const target = await makeRepo("gate-target");
    const config = await makeTempDir("gate-config");

    const result = runSync(target, config, [
      "--source", path.join(source, "skills/ess/ess-demo"), "--no-extract", "--dry-run",
      "--jargon-file", "company-jargon.json",
    ]);

    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stderr, /Looked for company-jargon\.json at:/);
  });

  it("exits 1 when CURSOR_API_KEY is missing", async () => {
    const config = await makeTempDir("gate-config");
    const env: NodeJS.ProcessEnv = { ...process.env, XDG_CONFIG_HOME: config };
    delete env.CURSOR_API_KEY;

    const result = spawnSync(
      process.execPath,
      [CLI, "sync", "--source", "/missing", "--dry-run"],
      { cwd: config, input: "", encoding: "utf8", env },
    );

    assert.equal(result.status, 1);
    assert.match(result.stderr, /CURSOR_API_KEY is not set/);
  });
});

describe("stageDryRunPlan", () => {
  it("stages the target in a temp repo seeded with the existing item, leaving the real target alone", async (t) => {
    t.mock.method(console, "log", () => {});
    const source = await makeRepo("dry-source", { "skills/ess/ess-demo/SKILL.md": "new\n" });
    const target = await makeRepo("dry-target", { "skills/ess/ess-demo/SKILL.md": "old\n" });
    const options = parseSyncArgs([
      "-s", path.join(source, "skills/ess/ess-demo"), "-r", target, "-t", "skills/ess/ess-demo", "--no-extract", "--dry-run",
    ]);
    assert.ok(options);

    const { plan: real } = await buildSyncPlan(options, { source: options.source, targetRepo: target });
    const staged = await stageDryRunPlan(options, real);
    stagingRepos.push(staged.targetRepoAbs);

    assert.notEqual(staged.targetRepoAbs, target);
    assert.equal(git(staged.targetRepoAbs, "rev-parse", "--is-inside-work-tree").trim(), "true");
    assert.equal(staged.mode, "SYNC");
    assert.equal(await fs.readFile(path.join(staged.targetAbs, "SKILL.md"), "utf8"), "old\n");
    assert.equal(staged.sourceAbs, real.sourceAbs);
    assert.equal(await fs.readFile(path.join(target, "skills/ess/ess-demo/SKILL.md"), "utf8"), "old\n");
  });

  it("stages the source repo too in extract mode, with only the files extract touches", async (t) => {
    t.mock.method(console, "log", () => {});
    const source = await makeRepo("dry-source", {
      "pyproject.toml": "[tool.uv.workspace]\nmembers = []\n",
      "tools/python/demo/pyproject.toml": "[project]\nname = \"demo\"\n",
      "tools/python/other/pyproject.toml": "[project]\nname = \"other\"\n",
    });
    const target = await makeRepo("dry-target");
    const options = parseSyncArgs(["-s", path.join(source, "tools/python/demo"), "-r", target, "--dry-run"]);
    assert.ok(options);

    const { plan: real } = await buildSyncPlan(options, { source: options.source, targetRepo: target });
    const staged = await stageDryRunPlan(options, real);
    assert.ok(staged.sourceRepoRoot);
    stagingRepos.push(staged.targetRepoAbs, staged.sourceRepoRoot);

    assert.notEqual(staged.sourceRepoRoot, source);
    assert.equal(staged.wrapperPkgAbs, path.join(staged.sourceRepoRoot, "tools/python/demo"));
    assert.equal(staged.extractedPkgAbs, path.join(staged.sourceRepoRoot, "packages/python/ess-demo"));
    await fs.access(path.join(staged.sourceRepoRoot, "pyproject.toml"));
    await fs.access(path.join(staged.sourceRepoRoot, "tools/python/demo/pyproject.toml"));
    await assert.rejects(fs.access(path.join(staged.sourceRepoRoot, "tools/python/other")));
  });
});

describe("loadEnvFiles", () => {
  it("reads the .env in the XDG config directory, without overriding the environment", async () => {
    const config = await makeTempDir("env-config");
    const cwd = await makeTempDir("env-cwd");
    await writeTree(path.join(config, "essentials-sync"), {
      ".env": "SYNC_TEST_FROM_FILE=file\nSYNC_TEST_PRESET=file\n",
    });
    const saved = process.env.XDG_CONFIG_HOME;
    process.env.XDG_CONFIG_HOME = config;
    process.env.SYNC_TEST_PRESET = "environment";
    try {
      const loaded = loadEnvFiles(cwd);

      assert.deepEqual(loaded, [path.join(config, "essentials-sync", ".env")]);
      assert.equal(process.env.SYNC_TEST_FROM_FILE, "file");
      assert.equal(process.env.SYNC_TEST_PRESET, "environment");
    } finally {
      if (saved === undefined) delete process.env.XDG_CONFIG_HOME;
      else process.env.XDG_CONFIG_HOME = saved;
      delete process.env.SYNC_TEST_FROM_FILE;
      delete process.env.SYNC_TEST_PRESET;
    }
  });
});
