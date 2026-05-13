import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { promises as fs } from "node:fs";
import path from "node:path";
import { tmpdir } from "node:os";
import {
  derivePackageName,
  deriveToolName,
  planExtract,
  validatePackageName,
} from "../src/extract-plan.js";

describe("derivePackageName", () => {
  it("prefixes bare names with ess-", () => {
    expect(derivePackageName("service-now-incident")).toBe("ess-service-now-incident");
    expect(derivePackageName("auth")).toBe("ess-auth");
  });

  it("leaves names that already start with ess- alone", () => {
    expect(derivePackageName("ess-auth")).toBe("ess-auth");
    expect(derivePackageName("ess-service-now-incident")).toBe("ess-service-now-incident");
  });
});

describe("validatePackageName", () => {
  it("accepts kebab-case ess-* names", () => {
    expect(validatePackageName("ess-auth")).toBe("ess-auth");
    expect(validatePackageName("ess-service-now-incident")).toBe("ess-service-now-incident");
  });

  it("rejects names that do not start with ess-", () => {
    expect(() => validatePackageName("auth")).toThrow(/must start with 'ess-'/);
    expect(() => validatePackageName("cisco-auth")).toThrow(/must start with 'ess-'/);
  });

  it("rejects non-kebab-case names", () => {
    expect(() => validatePackageName("ess_auth")).toThrow(/kebab-case/);
    expect(() => validatePackageName("EssAuth")).toThrow(/kebab-case/);
    expect(() => validatePackageName("ess-")).toThrow(/kebab-case/);
  });
});

describe("deriveToolName", () => {
  const sep = path.sep;

  it("extracts the tool name from a tools/python/<name> path", () => {
    expect(deriveToolName(["tools", "python", "service-now-incident"].join(sep))).toBe(
      "service-now-incident",
    );
    expect(deriveToolName(["tools", "python", "ess-auth"].join(sep))).toBe("ess-auth");
  });

  it("rejects paths that are not in tools/python/<name>", () => {
    expect(() => deriveToolName(["packages", "python", "ess-auth"].join(sep))).toThrow(
      /tools\/python\/<name>/,
    );
    expect(() => deriveToolName(["tools", "python", "foo", "src"].join(sep))).toThrow(
      /tools\/python\/<name>/,
    );
    expect(() => deriveToolName(["tools", "python"].join(sep))).toThrow(
      /tools\/python\/<name>/,
    );
  });

  it("rejects invalid kebab slugs", () => {
    expect(() => deriveToolName(["tools", "python", "Foo_Bar"].join(sep))).toThrow(
      /kebab-case/,
    );
  });
});

describe("planExtract", () => {
  let root: string;

  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(tmpdir(), "essentials-sync-extract-plan-"));
    await fs.mkdir(path.join(root, ".git"), { recursive: true });
    await fs.writeFile(path.join(root, ".git", "HEAD"), "ref: refs/heads/main\n");
  });

  afterEach(async () => {
    await fs.rm(root, { recursive: true, force: true });
  });

  async function makeTool(toolName: string): Promise<string> {
    const toolPath = path.join(root, "tools", "python", toolName);
    await fs.mkdir(toolPath, { recursive: true });
    await fs.writeFile(path.join(toolPath, "pyproject.toml"), `[project]\nname = "${toolName}"\n`);
    return toolPath;
  }

  it("derives the package name and paths for a generic tool", async () => {
    const toolPath = await makeTool("service-now-incident");

    const plan = await planExtract({ source: toolPath });

    expect(plan.names.toolName).toBe("service-now-incident");
    expect(plan.names.packageName).toBe("ess-service-now-incident");
    expect(plan.names.importableName).toBe("ess_service_now_incident");
    expect(plan.names.pyprojectMember).toBe("packages/python/ess-service-now-incident");
    expect(plan.names.defaultTargetPathRel).toBe("packages/python/ess-service-now-incident");
    expect(plan.sourceAbs).toBe(toolPath);
    expect(plan.sourceRepoRoot).toBe(root);
    expect(plan.extractedPkgAbs).toBe(
      path.join(root, "packages", "python", "ess-service-now-incident"),
    );
    expect(plan.wrapperPkgAbs).toBe(toolPath);
    expect(plan.alreadyExtracted).toBe(false);
  });

  it("preserves an existing ess- prefix instead of double-prefixing", async () => {
    const toolPath = await makeTool("ess-auth");

    const plan = await planExtract({ source: toolPath });

    expect(plan.names.packageName).toBe("ess-auth");
    expect(plan.names.importableName).toBe("ess_auth");
  });

  it("honors an explicit --package-name override", async () => {
    const toolPath = await makeTool("service-now-incident");

    const plan = await planExtract({
      source: toolPath,
      packageName: "ess-snow",
    });

    expect(plan.names.packageName).toBe("ess-snow");
    expect(plan.names.importableName).toBe("ess_snow");
    expect(plan.extractedPkgAbs).toBe(path.join(root, "packages", "python", "ess-snow"));
  });

  it("detects a pre-existing extracted package", async () => {
    const toolPath = await makeTool("service-now-incident");
    await fs.mkdir(path.join(root, "packages", "python", "ess-service-now-incident"), {
      recursive: true,
    });

    const plan = await planExtract({ source: toolPath });

    expect(plan.alreadyExtracted).toBe(true);
  });

  it("walks up from --source to find the git root automatically", async () => {
    const toolPath = await makeTool("service-now-incident");

    const plan = await planExtract({ source: toolPath });

    expect(plan.sourceRepoRoot).toBe(root);
  });

  it("respects an explicit --source-repo override", async () => {
    const toolPath = await makeTool("service-now-incident");

    const plan = await planExtract({
      source: toolPath,
      sourceRepo: root,
    });

    expect(plan.sourceRepoRoot).toBe(root);
  });

  it("rejects a --source that is outside --source-repo", async () => {
    const toolPath = await makeTool("service-now-incident");
    const otherRoot = await fs.mkdtemp(path.join(tmpdir(), "essentials-sync-other-"));
    try {
      await expect(
        planExtract({ source: toolPath, sourceRepo: otherRoot }),
      ).rejects.toThrow(/not inside/);
    } finally {
      await fs.rm(otherRoot, { recursive: true, force: true });
    }
  });

  it("rejects sources outside tools/python/<name>", async () => {
    const pkgPath = path.join(root, "packages", "python", "ess-auth");
    await fs.mkdir(pkgPath, { recursive: true });

    await expect(planExtract({ source: pkgPath })).rejects.toThrow(
      /tools\/python\/<name>/,
    );
  });
});
