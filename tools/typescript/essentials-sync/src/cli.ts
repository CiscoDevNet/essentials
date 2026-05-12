#!/usr/bin/env node
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Command } from "commander";
import chalk from "chalk";
import { CursorAgentError } from "@cursor/sdk";
import { runScanners, formatFindings } from "./scanners/index.js";
import { planSync, composeFullPlan } from "./sync.js";
import { planExtract } from "./extract-plan.js";
import { runSyncSession } from "./agent.js";
import {
  listAvailableModels,
  parseModelSpec,
  resolveModels,
} from "./model-resolver.js";

loadEnvFiles();

const DEFAULT_PRIMARY = "opus";
const DEFAULT_REVIEW = "codex";
const DEFAULT_MAX_REVISIONS = 3;

const program = new Command()
  .name("essentials-sync")
  .description(
    "Extract a jargon-free ess-* shared package out of a team-/account-specific tool"
    + " in the source repo, then sync that shared package to the open-source essentials repo."
    + " Default behavior runs both phases; pass --no-extract for sources that are already generic.",
  )
  .option("-s, --source <path>", "Absolute path to the source tool directory (tools/python/<name>/)")
  .option("-r, --target-repo <path>", "Absolute path to the target repo root (must be a git working tree)")
  .option("-t, --target-path <path>", "Path relative to --target-repo where the package should land (default: packages/python/<package-name>)")
  .option("--source-repo <path>", "Source repo root (default: git root of --source)")
  .option("--package-name <name>", "Name of the extracted ess-* package (default: derived from --source basename)")
  .option("-m, --model <spec>", "Primary agent model id, family sentinel, or 'auto'")
  .option("--review-model <spec>", "Adversarial reviewer model id, family sentinel, or 'auto'")
  .option("--max-revisions <n>", "Maximum scan-and-revise iterations per phase", parseInteger, DEFAULT_MAX_REVISIONS)
  .option("--dry-run", "Write everything to a temp directory instead of --target-path", false)
  .option("--no-source-scan", "Skip the informational source pre-scan")
  .option("--no-adversarial-review", "Skip the LLM reviewer; deterministic scanners only")
  .option("--no-extract", "Skip the in-source extract phase; assume --source is already a generic package and only run the sync to essentials")
  .option("--list-models", "Print the model catalog for the current API key and exit", false)
  .parse(process.argv);

void main(program);

async function main(cmd: Command): Promise<void> {
  const opts = cmd.opts();

  const apiKey = process.env.CURSOR_API_KEY ?? "";
  if (!apiKey) {
    fail(1, "CURSOR_API_KEY is not set. Export it or add it to .env.");
  }

  if (opts.listModels) {
    await handleListModels(apiKey);
    return;
  }

  const source = requireOption(opts.source as string | undefined, "--source");
  const targetRepo = requireOption(opts.targetRepo as string | undefined, "--target-repo");
  const explicitTargetPath = opts.targetPath as string | undefined;
  const sourceRepoOpt = opts.sourceRepo as string | undefined;
  const packageNameOpt = opts.packageName as string | undefined;

  const modelArg = (opts.model as string | undefined)
    ?? process.env.CURSOR_MODEL
    ?? DEFAULT_PRIMARY;
  const reviewModelArg = (opts.reviewModel as string | undefined)
    ?? process.env.CURSOR_REVIEW_MODEL
    ?? DEFAULT_REVIEW;

  const maxRevisions = (opts.maxRevisions as number | undefined) ?? DEFAULT_MAX_REVISIONS;
  const dryRun = Boolean(opts.dryRun);
  const noSourceScan = opts.sourceScan === false;
  const noAdversarial = opts.adversarialReview === false;
  const extractEnabled = opts.extract !== false;

  let extractHalf = null;
  if (extractEnabled) {
    try {
      extractHalf = await planExtract({
        source,
        sourceRepo: sourceRepoOpt,
        packageName: packageNameOpt,
      });
    } catch (error) {
      fail(1, error instanceof Error ? error.message : String(error));
    }
    if (extractHalf.alreadyExtracted) {
      console.log(
        chalk.yellow(
          `[extract] WARNING: ${extractHalf.extractedPkgAbs} already exists. `
            + `Re-running extract will overwrite it. Pass --no-extract to skip Phase A `
            + `and sync the existing extracted package as-is.`,
        ),
      );
    }
  }

  const resolvedTargetPath = explicitTargetPath
    ?? extractHalf?.names.defaultTargetPathRel
    ?? requireOption(undefined, "--target-path (required when --no-extract is set)");

  let syncHalf;
  let planTargetRepoForUx = targetRepo;
  try {
    const planTarget = dryRun
      ? await prepareDryRunTarget(resolvedTargetPath)
      : { repo: targetRepo, relPath: resolvedTargetPath };
    planTargetRepoForUx = planTarget.repo;
    const sourceForSync = extractHalf ? extractHalf.extractedPkgAbs : source;
    syncHalf = await planSync({
      source: sourceForSync,
      targetRepo: planTarget.repo,
      targetPath: planTarget.relPath,
      // When extract is enabled, the source will not exist until Phase A
      // materializes it, so we cannot assert existence here.
      assertSourceExists: !extractHalf,
    });
  } catch (error) {
    fail(1, error instanceof Error ? error.message : String(error));
  }

  const plan = composeFullPlan({ syncHalf, extractHalf });

  if (plan.phaseAEnabled) {
    console.log(
      chalk.cyan(
        `[plan] phase-A extract`
          + ` original=${plan.wrapperPkgAbs}`
          + ` extracted=${plan.extractedPkgAbs}`
          + ` package=${plan.packageName}`,
      ),
    );
  }
  console.log(
    chalk.cyan(
      `[plan] phase-B sync mode=${plan.mode} source=${plan.sourceAbs} target=${plan.targetAbs}`,
    ),
  );

  // Jargon overrides live next to the original source (the wrapper / current
  // tool directory). They apply to scans of both the extracted package and
  // the synced target.
  const jargonAnchor = plan.wrapperPkgAbs ?? plan.sourceAbs;
  const extraJargonTerms = await loadJargonOverrides(jargonAnchor);
  if (extraJargonTerms.length > 0) {
    console.log(
      chalk.dim(
        `[jargon] loaded ${extraJargonTerms.length} extra term(s) from .essentials-sync-jargon.json`,
      ),
    );
  }

  let sourceScan = null;
  if (!noSourceScan) {
    // Scan the original tool when extract is enabled (so the agent gets a
    // useful summary). For pure sync mode, scan the source directory.
    const sourceScanRoot = plan.wrapperPkgAbs ?? plan.sourceAbs;
    console.log(chalk.cyan(`[source-scan] running deterministic scanners on ${sourceScanRoot}`));
    sourceScan = await runScanners({
      rootPath: sourceScanRoot,
      jargonSeverity: "warning",
      extraJargonTerms,
    });
    console.log(
      chalk.dim(
        `[source-scan] ${sourceScan.findings.length} finding(s) in ${sourceScan.durationMs} ms`,
      ),
    );
  }

  let resolved;
  try {
    resolved = await resolveModels({
      apiKey,
      primarySpec: parseModelSpec(modelArg),
      reviewSpec: parseModelSpec(reviewModelArg),
    });
  } catch (error) {
    fail(1, `Could not resolve models via Cursor.models.list: ${error instanceof Error ? error.message : String(error)}`);
  }

  console.log(
    chalk.cyan(
      `[models] primary=${resolved.primary} (${resolved.primarySource})`
        + ` reviewer=${resolved.review} (${resolved.reviewSource})`,
    ),
  );
  if (resolved.collapsed) {
    console.log(
      chalk.yellow(
        "[models] WARNING: primary and reviewer resolved to the same model. Adversarial diversity is degraded.",
      ),
    );
  }

  try {
    const result = await runSyncSession({
      apiKey,
      primaryModel: resolved.primary,
      reviewModel: resolved.review,
      plan,
      sourceScan,
      maxRevisions,
      adversarialReview: !noAdversarial,
      extraJargonTerms,
    });

    if (result.status === "clean") {
      console.log(
        chalk.green(
          `[done] phase ${result.phase} clean after ${result.iterations} revision(s).`,
        ),
      );
      const reviewRoots: string[] = [];
      if (plan.phaseAEnabled && plan.sourceRepoRoot) {
        reviewRoots.push(`cd ${plan.sourceRepoRoot} && git status`);
      }
      reviewRoots.push(`cd ${planTargetRepoForUx} && git status`);
      for (const cmd of reviewRoots) {
        console.log(chalk.green(`[done] review your changes: ${cmd}`));
      }
      process.exit(0);
    }

    if (result.status === "exhausted-revisions") {
      console.log(
        chalk.red(
          `[fail] phase ${result.phase} still has ${result.remainingFindings.length} critical finding(s) `
            + `after ${result.iterations} revision(s).`,
        ),
      );
      const failedRoot = result.phase === "extract" ? plan.extractedPkgAbs ?? plan.targetAbs : plan.targetAbs;
      console.log(
        formatFindings({ findings: result.remainingFindings, scannedPaths: [failedRoot], durationMs: 0 }),
      );
      console.log(
        chalk.red(
          `[fail] tree left dirty for inspection. agent=${result.agentId} run=${result.lastRunId}`,
        ),
      );
      process.exit(2);
    }

    console.log(
      chalk.red(
        `[fail] phase ${result.phase} agent run failed mid-execution. agent=${result.agentId} run=${result.lastRunId}`,
      ),
    );
    if (result.errorMessage) {
      console.log(chalk.red(`[fail] SDK error: ${result.errorMessage}`));
    }
    process.exit(3);
  } catch (error) {
    if (error instanceof CursorAgentError) {
      console.error(
        chalk.red(
          `[fail] agent failed to start: ${error.message} (retryable=${
            (error as { isRetryable?: boolean }).isRetryable ?? "unknown"
          })`,
        ),
      );
      process.exit(1);
    }
    console.error(chalk.red(`[fail] unexpected error: ${error instanceof Error ? error.message : String(error)}`));
    process.exit(1);
  }
}

async function handleListModels(apiKey: string): Promise<void> {
  try {
    const models = await listAvailableModels(apiKey);
    if (models.length === 0) {
      console.log("No models returned from Cursor.models.list().");
      process.exit(0);
    }
    for (const id of models) {
      console.log(id);
    }
    process.exit(0);
  } catch (error) {
    fail(
      1,
      `Could not list models: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

async function loadJargonOverrides(sourceAbs: string): Promise<string[]> {
  const { promises: fs } = await import("node:fs");
  const path = await import("node:path");
  const configPath = path.join(sourceAbs, ".essentials-sync-jargon.json");
  try {
    const raw = await fs.readFile(configPath, "utf8");
    const parsed = JSON.parse(raw) as unknown;
    if (Array.isArray(parsed)) {
      return parsed.filter((entry): entry is string => typeof entry === "string");
    }
    if (parsed && typeof parsed === "object") {
      const terms = (parsed as { terms?: unknown }).terms;
      if (Array.isArray(terms)) {
        return terms.filter((entry): entry is string => typeof entry === "string");
      }
    }
    return [];
  } catch (error) {
    if (error instanceof Error && "code" in error && (error as { code?: string }).code === "ENOENT") {
      return [];
    }
    console.warn(
      chalk.yellow(`[jargon] could not read jargon overrides: ${(error as Error).message}`),
    );
    return [];
  }
}

async function prepareDryRunTarget(originalRelPath: string): Promise<{ repo: string; relPath: string }> {
  const { mkdtemp } = await import("node:fs/promises");
  const { tmpdir } = await import("node:os");
  const path = await import("node:path");
  const root = await mkdtemp(path.join(tmpdir(), "essentials-sync-dryrun-"));
  const { promises: fs } = await import("node:fs");
  await fs.mkdir(path.join(root, ".git"), { recursive: true });
  await fs.writeFile(path.join(root, ".git", "HEAD"), "ref: refs/heads/main\n", "utf8");
  console.log(chalk.dim(`[dry-run] target staged at ${root}`));
  return { repo: root, relPath: originalRelPath };
}

function requireOption(value: string | undefined, label: string): string {
  if (!value) {
    fail(1, `Missing required option ${label}.`);
  }
  return value;
}

function parseInteger(value: string): number {
  const n = Number.parseInt(value, 10);
  if (!Number.isFinite(n) || n < 0) {
    throw new Error(`Expected a non-negative integer, got: ${value}`);
  }
  return n;
}

function fail(exitCode: number, message: string): never {
  console.error(chalk.red(message));
  process.exit(exitCode);
}

function loadEnvFiles(): void {
  if (typeof process.loadEnvFile !== "function") return;
  const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const candidates = [
    path.resolve(process.cwd(), ".env"),
    path.resolve(packageRoot, ".env"),
  ];
  const seen = new Set<string>();
  for (const candidate of candidates) {
    if (seen.has(candidate)) continue;
    seen.add(candidate);
    try {
      process.loadEnvFile(candidate);
    } catch {
      // File missing or unreadable; silently skip. Each candidate is best-effort.
    }
  }
}
