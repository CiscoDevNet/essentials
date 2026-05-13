import { promises as fs } from "node:fs";
import path from "node:path";

const SLUG_RE = /^[a-z0-9][a-z0-9-]*[a-z0-9]$/;

export interface ExtractNames {
  toolName: string;
  packageName: string;
  importableName: string;
  pyprojectMember: string;
  defaultTargetPathRel: string;
}

export interface ExtractPlan {
  names: ExtractNames;
  sourceAbs: string;
  sourceRepoRoot: string;
  extractedPkgAbs: string;
  wrapperPkgAbs: string;
  alreadyExtracted: boolean;
}

export interface PlanExtractInputs {
  source: string;
  sourceRepo?: string;
  packageName?: string;
}

export async function planExtract({
  source,
  sourceRepo,
  packageName,
}: PlanExtractInputs): Promise<ExtractPlan> {
  const sourceAbs = path.resolve(source);
  await assertDirectory(sourceAbs, "--source");

  const sourceRepoRoot = sourceRepo
    ? path.resolve(sourceRepo)
    : await findGitRoot(sourceAbs);
  await assertDirectory(sourceRepoRoot, "--source-repo");

  const rel = path.relative(sourceRepoRoot, sourceAbs);
  if (rel.startsWith("..") || path.isAbsolute(rel)) {
    throw new Error(
      `--source (${sourceAbs}) is not inside --source-repo (${sourceRepoRoot})`,
    );
  }

  const toolName = deriveToolName(rel);
  const finalPackageName = packageName
    ? validatePackageName(packageName)
    : derivePackageName(toolName);
  const importableName = finalPackageName.replaceAll("-", "_");
  const pyprojectMember = ["packages", "python", finalPackageName].join("/");
  const extractedPkgAbs = path.join(
    sourceRepoRoot,
    "packages",
    "python",
    finalPackageName,
  );
  const wrapperPkgAbs = sourceAbs;
  const alreadyExtracted = await directoryExists(extractedPkgAbs);

  return {
    names: {
      toolName,
      packageName: finalPackageName,
      importableName,
      pyprojectMember,
      defaultTargetPathRel: pyprojectMember,
    },
    sourceAbs,
    sourceRepoRoot,
    extractedPkgAbs,
    wrapperPkgAbs,
    alreadyExtracted,
  };
}

export function deriveToolName(relPathFromRepoRoot: string): string {
  const parts = relPathFromRepoRoot.split(path.sep).filter((seg) => seg.length > 0);
  if (parts.length !== 3 || parts[0] !== "tools" || parts[1] !== "python") {
    throw new Error(
      `Extract requires --source to point at a tools/python/<name> directory `
        + `inside the source repo. Got relative path: '${relPathFromRepoRoot}'`,
    );
  }
  const name = parts[2];
  if (!name || !SLUG_RE.test(name)) {
    throw new Error(
      `Invalid tool name derived from --source: '${name}'. `
        + `Expected kebab-case slug (lowercase letters, digits, hyphens).`,
    );
  }
  return name;
}

export function derivePackageName(toolName: string): string {
  if (toolName.startsWith("ess-")) {
    return toolName;
  }
  return `ess-${toolName}`;
}

export function validatePackageName(raw: string): string {
  const trimmed = raw.trim();
  if (!SLUG_RE.test(trimmed)) {
    throw new Error(
      `--package-name must be a kebab-case slug (got: '${raw}')`,
    );
  }
  if (!trimmed.startsWith("ess-")) {
    throw new Error(
      `--package-name must start with 'ess-' so the extracted package is recognizable `
        + `as an open-sourcable shared library (got: '${raw}').`,
    );
  }
  return trimmed;
}

async function findGitRoot(start: string): Promise<string> {
  let current = path.resolve(start);
  // Path traversal terminates at the filesystem root, where dirname(p) === p.
  for (;;) {
    if (await pathExists(path.join(current, ".git"))) {
      return current;
    }
    const parent = path.dirname(current);
    if (parent === current) {
      throw new Error(
        `Could not find a git repo root at or above ${start}. `
          + `Pass --source-repo explicitly.`,
      );
    }
    current = parent;
  }
}

async function assertDirectory(absPath: string, label: string): Promise<void> {
  try {
    const stat = await fs.stat(absPath);
    if (!stat.isDirectory()) {
      throw new Error(`${label} is not a directory: ${absPath}`);
    }
  } catch (error) {
    if (isNotFoundError(error)) {
      throw new Error(`${label} does not exist: ${absPath}`);
    }
    throw error;
  }
}

async function directoryExists(p: string): Promise<boolean> {
  try {
    const stat = await fs.stat(p);
    return stat.isDirectory();
  } catch (error) {
    if (isNotFoundError(error)) return false;
    throw error;
  }
}

async function pathExists(p: string): Promise<boolean> {
  try {
    await fs.stat(p);
    return true;
  } catch (error) {
    if (isNotFoundError(error)) return false;
    throw error;
  }
}

function isNotFoundError(error: unknown): boolean {
  if (error && typeof error === "object") {
    const code = (error as { code?: string }).code;
    return code === "ENOENT";
  }
  return false;
}
