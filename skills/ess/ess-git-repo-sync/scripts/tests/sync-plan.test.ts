import assert from "node:assert/strict";
import { promises as fs } from "node:fs";
import path from "node:path";
import { afterEach, describe, it } from "node:test";
import { planSync } from "../src/sync.ts";
import { makeRepo, removeTempDirs } from "./temp-repos.ts";

afterEach(removeTempDirs);

describe("planSync", () => {
  it("plans a copy of a single instruction file when the target is missing", async () => {
    const sourceRepo = await makeRepo("sync-plan-source");
    const targetRepo = await makeRepo("sync-plan-target");
    const source = path.join(sourceRepo, "instructions", "ess", "ess-apm-sources.instructions.md");
    await fs.mkdir(path.dirname(source), { recursive: true });
    await fs.writeFile(source, "# APM Sources\n");

    const plan = await planSync({
      source,
      targetRepo,
      targetPath: "instructions/ess/ess-apm-sources.instructions.md",
    });

    assert.equal(plan.mode, "COPY");
    assert.equal(plan.sourceAbs, source);
    assert.equal(plan.targetAbs, path.join(targetRepo, "instructions", "ess", "ess-apm-sources.instructions.md"));
    assert.equal(plan.phaseAEnabled, false);
  });

  it("plans a sync when the target file already exists", async () => {
    const sourceRepo = await makeRepo("sync-plan-source");
    const targetRepo = await makeRepo("sync-plan-target");
    const source = path.join(sourceRepo, "instructions", "ess", "ess-rule.instructions.md");
    const target = path.join(targetRepo, "instructions", "ess", "ess-rule.instructions.md");
    await fs.mkdir(path.dirname(source), { recursive: true });
    await fs.mkdir(path.dirname(target), { recursive: true });
    await fs.writeFile(source, "# Rule\n");
    await fs.writeFile(target, "# Rule\n");

    const plan = await planSync({
      source,
      targetRepo,
      targetPath: "instructions/ess/ess-rule.instructions.md",
    });

    assert.equal(plan.mode, "SYNC");
    assert.equal(plan.targetAbs, target);
  });

  it("still accepts a directory source", async () => {
    const sourceRepo = await makeRepo("sync-plan-source");
    const targetRepo = await makeRepo("sync-plan-target");
    const source = path.join(sourceRepo, "packages", "python", "ess-demo");
    await fs.mkdir(source, { recursive: true });

    const plan = await planSync({ source, targetRepo, targetPath: "packages/python/ess-demo" });

    assert.equal(plan.mode, "COPY");
    assert.equal(plan.sourceAbs, source);
  });

  it("rejects a missing source", async () => {
    const targetRepo = await makeRepo("sync-plan-target");

    await assert.rejects(
      planSync({
        source: path.join(targetRepo, "missing.md"),
        targetRepo,
        targetPath: "instructions/ess/missing.md",
      }),
      /does not exist/,
    );
  });
});
