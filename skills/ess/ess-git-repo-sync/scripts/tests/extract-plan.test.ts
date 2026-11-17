import assert from "node:assert/strict";
import { promises as fs } from "node:fs";
import path from "node:path";
import { afterEach, beforeEach, describe, it } from "node:test";
import {
  derivePackageName,
  deriveToolName,
  planExtract,
  validatePackageName,
} from "../src/extract-plan.ts";
import { makeRepo, makeTempDir, removeTempDirs } from "./temp-repos.ts";

describe("derivePackageName", () => {
  it("prefixes bare names with ess-", () => {
    assert.equal(derivePackageName("service-now-incident"), "ess-service-now-incident");
    assert.equal(derivePackageName("auth"), "ess-auth");
  });

  it("leaves names that already start with ess- alone", () => {
    assert.equal(derivePackageName("ess-auth"), "ess-auth");
    assert.equal(derivePackageName("ess-service-now-incident"), "ess-service-now-incident");
  });
});

describe("validatePackageName", () => {
  it("accepts kebab-case ess-* names", () => {
    assert.equal(validatePackageName("ess-auth"), "ess-auth");
    assert.equal(validatePackageName("ess-service-now-incident"), "ess-service-now-incident");
  });

  it("rejects names that do not start with ess-", () => {
    assert.throws(() => validatePackageName("auth"), /must start with 'ess-'/);
    assert.throws(() => validatePackageName("corp-auth"), /must start with 'ess-'/);
  });

  it("rejects non-kebab-case names", () => {
    assert.throws(() => validatePackageName("ess_auth"), /kebab-case/);
    assert.throws(() => validatePackageName("EssAuth"), /kebab-case/);
    assert.throws(() => validatePackageName("ess-"), /kebab-case/);
  });
});

describe("deriveToolName", () => {
  const sep = path.sep;

  it("extracts the tool name from a tools/python/<name> path", () => {
    assert.equal(deriveToolName(["tools", "python", "service-now-incident"].join(sep)), "service-now-incident");
    assert.equal(deriveToolName(["tools", "python", "ess-auth"].join(sep)), "ess-auth");
  });

  it("rejects paths that are not in tools/python/<name>", () => {
    assert.throws(() => deriveToolName(["packages", "python", "ess-auth"].join(sep)), /tools\/python\/<name>/);
    assert.throws(() => deriveToolName(["tools", "python", "foo", "src"].join(sep)), /tools\/python\/<name>/);
    assert.throws(() => deriveToolName(["tools", "python"].join(sep)), /tools\/python\/<name>/);
  });

  it("rejects invalid kebab slugs", () => {
    assert.throws(() => deriveToolName(["tools", "python", "Foo_Bar"].join(sep)), /kebab-case/);
  });
});

describe("planExtract", () => {
  let root: string;

  beforeEach(async () => {
    root = await makeRepo("extract-plan");
  });

  afterEach(removeTempDirs);

  async function makeTool(toolName: string): Promise<string> {
    const toolPath = path.join(root, "tools", "python", toolName);
    await fs.mkdir(toolPath, { recursive: true });
    await fs.writeFile(path.join(toolPath, "pyproject.toml"), `[project]\nname = "${toolName}"\n`);
    return toolPath;
  }

  it("derives the package name and paths for a generic tool", async () => {
    const toolPath = await makeTool("service-now-incident");

    const plan = await planExtract({ source: toolPath });

    assert.equal(plan.names.toolName, "service-now-incident");
    assert.equal(plan.names.packageName, "ess-service-now-incident");
    assert.equal(plan.names.importableName, "ess_service_now_incident");
    assert.equal(plan.names.pyprojectMember, "packages/python/ess-service-now-incident");
    assert.equal(plan.names.defaultTargetPathRel, "packages/python/ess-service-now-incident");
    assert.equal(plan.sourceAbs, toolPath);
    assert.equal(plan.sourceRepoRoot, root);
    assert.equal(plan.extractedPkgAbs, path.join(root, "packages", "python", "ess-service-now-incident"));
    assert.equal(plan.wrapperPkgAbs, toolPath);
    assert.equal(plan.alreadyExtracted, false);
  });

  it("preserves an existing ess- prefix instead of double-prefixing", async () => {
    const toolPath = await makeTool("ess-auth");

    const plan = await planExtract({ source: toolPath });

    assert.equal(plan.names.packageName, "ess-auth");
    assert.equal(plan.names.importableName, "ess_auth");
  });

  it("honors an explicit --package-name override", async () => {
    const toolPath = await makeTool("service-now-incident");

    const plan = await planExtract({ source: toolPath, packageName: "ess-snow" });

    assert.equal(plan.names.packageName, "ess-snow");
    assert.equal(plan.names.importableName, "ess_snow");
    assert.equal(plan.extractedPkgAbs, path.join(root, "packages", "python", "ess-snow"));
  });

  it("detects a pre-existing extracted package", async () => {
    const toolPath = await makeTool("service-now-incident");
    await fs.mkdir(path.join(root, "packages", "python", "ess-service-now-incident"), { recursive: true });

    const plan = await planExtract({ source: toolPath });

    assert.equal(plan.alreadyExtracted, true);
  });

  it("walks up from --source to find the git root automatically", async () => {
    const toolPath = await makeTool("service-now-incident");

    const plan = await planExtract({ source: toolPath });

    assert.equal(plan.sourceRepoRoot, root);
  });

  it("respects an explicit --source-repo override", async () => {
    const toolPath = await makeTool("service-now-incident");

    const plan = await planExtract({ source: toolPath, sourceRepo: root });

    assert.equal(plan.sourceRepoRoot, root);
  });

  it("rejects a --source that is outside --source-repo", async () => {
    const toolPath = await makeTool("service-now-incident");
    const otherRoot = await makeTempDir("extract-plan-other");

    await assert.rejects(planExtract({ source: toolPath, sourceRepo: otherRoot }), /not inside/);
  });

  it("rejects sources outside tools/python/<name>", async () => {
    const pkgPath = path.join(root, "packages", "python", "ess-auth");
    await fs.mkdir(pkgPath, { recursive: true });

    await assert.rejects(planExtract({ source: pkgPath }), /tools\/python\/<name>/);
  });
});
