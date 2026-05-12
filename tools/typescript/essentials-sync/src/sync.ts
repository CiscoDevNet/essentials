import { promises as fs } from "node:fs";
import path from "node:path";
import type { SyncMode, SyncPlan } from "./types.js";
import type { ExtractPlan } from "./extract-plan.js";

export interface PlanSyncInputs {
  source: string;
  targetRepo: string;
  targetPath: string;
  // When extract is enabled the source does not exist on disk yet -- Phase A
  // will create it. Skip the existence check in that case.
  assertSourceExists?: boolean;
}

export async function planSync({
  source,
  targetRepo,
  targetPath,
  assertSourceExists = true,
}: PlanSyncInputs): Promise<SyncPlan> {
  const sourceAbs = path.resolve(source);
  const targetRepoAbs = path.resolve(targetRepo);
  const targetPathRel = path.normalize(targetPath);
  const targetAbs = path.join(targetRepoAbs, targetPathRel);

  if (assertSourceExists) {
    await assertDirectoryExists(sourceAbs, "--source");
  }
  await assertDirectoryExists(targetRepoAbs, "--target-repo");
  await assertGitWorkingTree(targetRepoAbs);

  const mode: SyncMode = (await directoryExists(targetAbs)) ? "SYNC" : "COPY";

  return {
    mode,
    sourceAbs,
    targetRepoAbs,
    targetPathRel,
    targetAbs,
    phaseAEnabled: false,
  };
}

export interface ComposeFullPlanInputs {
  syncHalf: SyncPlan;
  extractHalf: ExtractPlan | null;
}

// Combines the two half-plans into a single SyncPlan. When `extractHalf` is
// null we have a pure sync (legacy mode); when present we add the Phase A
// extract metadata and override `sourceAbs` to point at where Phase A will
// drop the extracted package.
export function composeFullPlan({
  syncHalf,
  extractHalf,
}: ComposeFullPlanInputs): SyncPlan {
  if (!extractHalf) {
    return syncHalf;
  }
  return {
    ...syncHalf,
    sourceAbs: extractHalf.extractedPkgAbs,
    phaseAEnabled: true,
    extractedPkgAbs: extractHalf.extractedPkgAbs,
    wrapperPkgAbs: extractHalf.wrapperPkgAbs,
    sourceRepoRoot: extractHalf.sourceRepoRoot,
    originalToolName: extractHalf.names.toolName,
    packageName: extractHalf.names.packageName,
    importableName: extractHalf.names.importableName,
  };
}

async function assertDirectoryExists(absPath: string, label: string): Promise<void> {
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

async function assertGitWorkingTree(repoPath: string): Promise<void> {
  const gitDir = path.join(repoPath, ".git");
  if (!(await directoryExists(gitDir)) && !(await fileExists(gitDir))) {
    throw new Error(`--target-repo is not a git working tree (missing .git): ${repoPath}`);
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

async function fileExists(p: string): Promise<boolean> {
  try {
    const stat = await fs.stat(p);
    return stat.isFile();
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
