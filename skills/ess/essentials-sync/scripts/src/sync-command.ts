import path from "node:path";
import { parseArgs } from "node:util";
import { runSyncSession } from "./agent.ts";
import { parseNonNegativeInteger, rethrowAsUsageError, UsageError } from "./args.ts";
import { confirmWrite } from "./confirm.ts";
import { createStagingRepo, seedStagingRepo, stageExtractSource } from "./dry-run.ts";
import { planExtract } from "./extract-plan.ts";
import { loadJargonOverrides } from "./jargon-overrides.ts";
import { parseModelSpec, resolveModels } from "./model-resolver.ts";
import { PROGRAM_NAME } from "./program.ts";
import { formatFindings, runScanners } from "./scanners/index.ts";
import { loadCursorSdk } from "./sdk.ts";
import { style } from "./style.ts";
import { composeFullPlan, planSync } from "./sync.ts";
import type { ResolvedModels, ScanReport, SyncPlan } from "./types.ts";

const DEFAULT_PRIMARY = "opus";
const DEFAULT_REVIEW = "codex";
const DEFAULT_MAX_REVISIONS = 3;

export const SYNC_HELP = `Usage: ${PROGRAM_NAME} sync --source <path> --target-repo <path> [options]

Extract a jargon-free ess-* package out of a tool in the source repo, then
sync it into the target repo. Both phases run by default; pass --no-extract
for a source that is already generic. Writes to the source repo (extract) and
the target repo (sync), so it asks for confirmation first.

Options:
  -s, --source <path>       The item to sync. Extract mode: a tools/python/<name>
                            directory. With --no-extract: a directory or one file
  -r, --target-repo <path>  Root of the target repo (a git work tree)
  -t, --target-path <path>  Where the item lands, relative to --target-repo
                            (default in extract mode: packages/python/<package-name>;
                            required with --no-extract)
  --source-repo <path>      Source repo root (default: the git root of --source)
  --package-name <name>     Name of the extracted ess-* package
                            (default: ess-<basename of --source>)
  -m, --model <spec>        Primary model: an id, a family (opus, codex, claude,
                            gpt, gemini, composer), or auto (default: ${DEFAULT_PRIMARY})
  --review-model <spec>     Adversarial reviewer model, same forms (default: ${DEFAULT_REVIEW})
  --max-revisions <n>       Scan-and-revise iterations per phase (default: ${DEFAULT_MAX_REVISIONS})
  --dry-run                 Run everything against staging copies in a temp
                            directory; the real repos are not touched
  -y, --yes                 Skip the confirmation prompt
  --no-extract              Skip the extract phase; --source is already generic
  --no-fast-copy            Always let the primary agent author the sync
  --no-source-scan          Skip the informational scan of the source
  --no-adversarial-review   Deterministic scanners only; no LLM reviewer
  -h, --help                Show this help

Environment:
  CURSOR_API_KEY            Required. Read from the environment, ./.env, or
                            the ${PROGRAM_NAME} .env in your XDG config directory
  CURSOR_MODEL              Default for --model
  CURSOR_REVIEW_MODEL       Default for --review-model

Exit codes: 0 clean, 1 could not start, 2 critical findings remain after
--max-revisions, 3 the agent failed mid-run.`;

export interface SyncOptions {
  source: string;
  targetRepo: string;
  targetPath?: string;
  sourceRepo?: string;
  packageName?: string;
  model: string;
  reviewModel: string;
  maxRevisions: number;
  dryRun: boolean;
  yes: boolean;
  extract: boolean;
  fastCopy: boolean;
  sourceScan: boolean;
  adversarialReview: boolean;
}

export interface SyncIo {
  isInteractive: boolean;
  ask?: (question: string) => Promise<string>;
}

// Returns null for --help.
export function parseSyncArgs(argv: string[]): SyncOptions | null {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      allowNegative: true,
      options: {
        source: { type: "string", short: "s" },
        "target-repo": { type: "string", short: "r" },
        "target-path": { type: "string", short: "t" },
        "source-repo": { type: "string" },
        "package-name": { type: "string" },
        model: { type: "string", short: "m" },
        "review-model": { type: "string" },
        "max-revisions": { type: "string" },
        "dry-run": { type: "boolean", default: false },
        yes: { type: "boolean", short: "y", default: false },
        extract: { type: "boolean", default: true },
        "fast-copy": { type: "boolean", default: true },
        "source-scan": { type: "boolean", default: true },
        "adversarial-review": { type: "boolean", default: true },
        help: { type: "boolean", short: "h" },
      },
    });
  } catch (error) {
    rethrowAsUsageError(error);
  }
  const { values } = parsed;
  if (values.help) return null;

  const source = values.source;
  const targetRepo = values["target-repo"];
  if (!source) throw new UsageError("sync needs --source.");
  if (!targetRepo) throw new UsageError("sync needs --target-repo.");
  if (!values.extract && !values["target-path"]) {
    throw new UsageError("--target-path is required with --no-extract.");
  }

  return {
    source,
    targetRepo,
    targetPath: values["target-path"],
    sourceRepo: values["source-repo"],
    packageName: values["package-name"],
    model: values.model ?? process.env.CURSOR_MODEL ?? DEFAULT_PRIMARY,
    reviewModel: values["review-model"] ?? process.env.CURSOR_REVIEW_MODEL ?? DEFAULT_REVIEW,
    maxRevisions: values["max-revisions"] === undefined
      ? DEFAULT_MAX_REVISIONS
      : parseNonNegativeInteger(values["max-revisions"], "--max-revisions"),
    dryRun: values["dry-run"],
    yes: values.yes,
    extract: values.extract,
    fastCopy: values["fast-copy"],
    sourceScan: values["source-scan"],
    adversarialReview: values["adversarial-review"],
  };
}

interface PlanLocations {
  source: string;
  sourceRepo?: string;
  targetRepo: string;
}

interface BuiltPlan {
  plan: SyncPlan;
  alreadyExtracted: boolean;
}

// Validates the arguments against the filesystem and derives every path the
// run will touch. The dry run calls it again on the staging repos, so both
// runs take the same code path.
export async function buildSyncPlan(options: SyncOptions, locations: PlanLocations): Promise<BuiltPlan> {
  const extractHalf = options.extract
    ? await planExtract({
        source: locations.source,
        sourceRepo: locations.sourceRepo,
        packageName: options.packageName,
      })
    : null;
  const targetPath = options.targetPath ?? extractHalf?.names.defaultTargetPathRel;
  if (!targetPath) {
    throw new UsageError("--target-path is required with --no-extract.");
  }
  const syncHalf = await planSync({
    source: extractHalf ? extractHalf.extractedPkgAbs : locations.source,
    targetRepo: locations.targetRepo,
    targetPath,
    // Phase A creates the extracted package, so it need not exist yet.
    assertSourceExists: !extractHalf,
  });
  return {
    plan: composeFullPlan({ syncHalf, extractHalf }),
    alreadyExtracted: extractHalf?.alreadyExtracted ?? false,
  };
}

// Rebuilds the plan against staging repos in the temp directory, seeded with
// what the real run would read, so a dry run writes nothing outside it.
export async function stageDryRunPlan(options: SyncOptions, real: SyncPlan): Promise<SyncPlan> {
  const targetRepo = await createStagingRepo("target");
  await seedStagingRepo(real.targetRepoAbs, targetRepo, [real.targetPathRel]);
  console.log(style.dim(`[dry-run] target staged at ${targetRepo}`));

  if (!real.phaseAEnabled || !real.sourceRepoRoot || !real.wrapperPkgAbs || !real.extractedPkgAbs) {
    return (await buildSyncPlan(options, { source: real.sourceAbs, targetRepo })).plan;
  }

  const sourceRepoRoot = real.sourceRepoRoot;
  const toolRel = path.relative(sourceRepoRoot, real.wrapperPkgAbs);
  const extractedRel = path.relative(sourceRepoRoot, real.extractedPkgAbs);
  const sourceRepo = await stageExtractSource(sourceRepoRoot, [toolRel, extractedRel]);
  console.log(style.dim(`[dry-run] source staged at ${sourceRepo}`));
  return (
    await buildSyncPlan(options, { source: path.join(sourceRepo, toolRel), sourceRepo, targetRepo })
  ).plan;
}

export async function runSyncCommand(
  argv: string[],
  io: SyncIo = { isInteractive: Boolean(process.stdin.isTTY) },
): Promise<number> {
  const options = parseSyncArgs(argv);
  if (!options) {
    console.log(SYNC_HELP);
    return 0;
  }

  const apiKey = process.env.CURSOR_API_KEY ?? "";
  if (!apiKey) {
    throw new Error(
      "CURSOR_API_KEY is not set. Export it, or put it in ./.env or the "
        + `${PROGRAM_NAME} .env in your XDG config directory (see references/cursor-sdk.md).`,
    );
  }

  const { plan: realPlan, alreadyExtracted } = await buildSyncPlan(options, {
    source: options.source,
    sourceRepo: options.sourceRepo,
    targetRepo: options.targetRepo,
  });
  logPlan(realPlan, alreadyExtracted);

  // Fail before the slow steps when consent can never be given.
  if (!options.dryRun && !options.yes && !io.isInteractive) {
    throw new Error(
      "sync writes to the repos above and there is no terminal to confirm on. "
        + "Re-run with --yes to confirm, or with --dry-run to stage the run in a temp directory.",
    );
  }

  // Jargon overrides live next to the original source (the wrapper, or the
  // item itself). They apply to scans of both the extracted package and the
  // synced target.
  const jargonAnchor = realPlan.wrapperPkgAbs ?? realPlan.sourceAbs;
  const extraJargonTerms = await loadJargonOverrides(jargonAnchor);
  if (extraJargonTerms.length > 0) {
    console.log(style.dim(`[jargon] loaded ${extraJargonTerms.length} extra term(s)`));
  }

  let sourceScan: ScanReport | null = null;
  if (options.sourceScan) {
    // Scan the original tool when extract is enabled, so the agent gets a
    // useful summary; otherwise the item being synced.
    const sourceScanRoot = realPlan.wrapperPkgAbs ?? realPlan.sourceAbs;
    console.log(style.cyan(`[source-scan] running deterministic scanners on ${sourceScanRoot}`));
    sourceScan = await runScanners({
      rootPath: sourceScanRoot,
      jargonSeverity: "warning",
      extraJargonTerms,
    });
    console.log(
      style.dim(`[source-scan] ${sourceScan.findings.length} finding(s) in ${sourceScan.durationMs} ms`),
    );
  }

  let models: ResolvedModels;
  try {
    models = await resolveModels({
      apiKey,
      primarySpec: parseModelSpec(options.model),
      reviewSpec: parseModelSpec(options.reviewModel),
    });
  } catch (error) {
    throw new Error(`Could not resolve models via Cursor.models.list: ${errorMessage(error)}`);
  }
  console.log(
    style.cyan(
      `[models] primary=${models.primary} (${models.primarySource})`
        + ` reviewer=${models.review} (${models.reviewSource})`,
    ),
  );
  if (models.collapsed) {
    console.log(
      style.yellow(
        "[models] WARNING: primary and reviewer resolved to the same model. Adversarial diversity is degraded.",
      ),
    );
  }

  const outcome = await confirmWrite({
    dryRun: options.dryRun,
    yes: options.yes,
    isInteractive: io.isInteractive,
    question: `Write to ${describeWrites(realPlan)}?`,
    ask: io.ask,
  });
  if (outcome === "needs-yes") {
    throw new Error("No terminal to confirm on; re-run with --yes.");
  }
  if (outcome === "declined") {
    console.error("Aborted. Nothing was written.");
    return 1;
  }

  const plan = outcome === "dry-run" ? await stageDryRunPlan(options, realPlan) : realPlan;
  return runSession({ apiKey, models, plan, sourceScan, extraJargonTerms, options });
}

interface RunSessionInputs {
  apiKey: string;
  models: ResolvedModels;
  plan: SyncPlan;
  sourceScan: ScanReport | null;
  extraJargonTerms: string[];
  options: SyncOptions;
}

async function runSession({
  apiKey,
  models,
  plan,
  sourceScan,
  extraJargonTerms,
  options,
}: RunSessionInputs): Promise<number> {
  try {
    const result = await runSyncSession({
      apiKey,
      primaryModel: models.primary,
      reviewModel: models.review,
      plan,
      sourceScan,
      maxRevisions: options.maxRevisions,
      adversarialReview: options.adversarialReview,
      extraJargonTerms,
      fastCopy: options.fastCopy,
    });

    if (result.status === "clean") {
      console.log(style.green(`[done] phase ${result.phase} clean after ${result.iterations} revision(s).`));
      const reviewRepos = plan.phaseAEnabled && plan.sourceRepoRoot
        ? [plan.sourceRepoRoot, plan.targetRepoAbs]
        : [plan.targetRepoAbs];
      for (const repo of reviewRepos) {
        console.log(style.green(`[done] review your changes: cd ${repo} && git status`));
      }
      return 0;
    }

    if (result.status === "exhausted-revisions") {
      console.log(
        style.red(
          `[fail] phase ${result.phase} still has ${result.remainingFindings.length} critical finding(s) `
            + `after ${result.iterations} revision(s).`,
        ),
      );
      const failedRoot = result.phase === "extract" ? plan.extractedPkgAbs ?? plan.targetAbs : plan.targetAbs;
      console.log(
        formatFindings({ findings: result.remainingFindings, scannedPaths: [failedRoot], durationMs: 0 }),
      );
      console.log(
        style.red(`[fail] tree left dirty for inspection. agent=${result.agentId} run=${result.lastRunId}`),
      );
      return 2;
    }

    console.log(
      style.red(
        `[fail] phase ${result.phase} agent run failed mid-execution. agent=${result.agentId} run=${result.lastRunId}`,
      ),
    );
    if (result.errorMessage) {
      console.log(style.red(`[fail] SDK error: ${result.errorMessage}`));
    }
    return 3;
  } catch (error) {
    const sdk = await loadCursorSdk().catch(() => null);
    if (sdk && error instanceof sdk.CursorAgentError) {
      const retryable = (error as { isRetryable?: boolean }).isRetryable ?? "unknown";
      throw new Error(`agent failed to start: ${error.message} (retryable=${retryable})`);
    }
    throw error;
  }
}

function logPlan(plan: SyncPlan, alreadyExtracted: boolean): void {
  if (plan.phaseAEnabled) {
    console.log(
      style.cyan(
        `[plan] phase-A extract original=${plan.wrapperPkgAbs} extracted=${plan.extractedPkgAbs}`
          + ` package=${plan.packageName}`,
      ),
    );
    if (alreadyExtracted) {
      console.log(
        style.yellow(
          `[extract] WARNING: ${plan.extractedPkgAbs} already exists. Re-running extract will `
            + "overwrite it. Pass --no-extract to sync the existing extracted package as-is.",
        ),
      );
    }
  }
  console.log(
    style.cyan(`[plan] phase-B sync mode=${plan.mode} source=${plan.sourceAbs} target=${plan.targetAbs}`),
  );
}

function describeWrites(plan: SyncPlan): string {
  return plan.phaseAEnabled && plan.sourceRepoRoot
    ? `${plan.sourceRepoRoot} (extract) and ${plan.targetAbs} (sync)`
    : plan.targetAbs;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
