import { afterEach, describe, expect, it } from "vitest";
import { promises as fs } from "node:fs";
import path from "node:path";
import os from "node:os";
import { planSync } from "../src/sync.js";

const tempRoots: string[] = [];

async function makeRepo(): Promise<string> {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "sync-plan-"));
  tempRoots.push(root);
  await fs.mkdir(path.join(root, ".git"));
  return root;
}

afterEach(async () => {
  while (tempRoots.length > 0) {
    const root = tempRoots.pop();
    if (root) await fs.rm(root, { recursive: true, force: true });
  }
});

describe("planSync", () => {
  it("plans a copy of a single instruction file when the target is missing", async () => {
    const sourceRepo = await makeRepo();
    const targetRepo = await makeRepo();
    const source = path.join(sourceRepo, "instructions", "ess", "ess-apm-sources.instructions.md");
    await fs.mkdir(path.dirname(source), { recursive: true });
    await fs.writeFile(source, "# APM Sources\n");

    const plan = await planSync({
      source,
      targetRepo,
      targetPath: "instructions/ess/ess-apm-sources.instructions.md",
    });

    expect(plan.mode).toBe("COPY");
    expect(plan.sourceAbs).toBe(source);
    expect(plan.targetAbs).toBe(
      path.join(targetRepo, "instructions", "ess", "ess-apm-sources.instructions.md"),
    );
    expect(plan.phaseAEnabled).toBe(false);
  });

  it("plans a sync when the target file already exists", async () => {
    const sourceRepo = await makeRepo();
    const targetRepo = await makeRepo();
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

    expect(plan.mode).toBe("SYNC");
    expect(plan.targetAbs).toBe(target);
  });

  it("still accepts a directory source", async () => {
    const sourceRepo = await makeRepo();
    const targetRepo = await makeRepo();
    const source = path.join(sourceRepo, "packages", "python", "ess-demo");
    await fs.mkdir(source, { recursive: true });

    const plan = await planSync({
      source,
      targetRepo,
      targetPath: "packages/python/ess-demo",
    });

    expect(plan.mode).toBe("COPY");
    expect(plan.sourceAbs).toBe(source);
  });

  it("rejects a missing source", async () => {
    const targetRepo = await makeRepo();

    await expect(
      planSync({
        source: path.join(targetRepo, "missing.md"),
        targetRepo,
        targetPath: "instructions/ess/missing.md",
      }),
    ).rejects.toThrow(/does not exist/);
  });
});
