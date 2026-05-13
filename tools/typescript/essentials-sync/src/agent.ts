import { Agent } from "@cursor/sdk";
import type { SDKAgent } from "@cursor/sdk";
import chalk from "chalk";
import type { Finding, ScanReport, SyncPlan } from "./types.js";
import {
  EXTRACT_SYSTEM_PROMPT,
  SYNC_SYSTEM_PROMPT,
  buildExtractInitialPrompt,
  buildExtractRevisionPrompt,
  buildSyncInitialPrompt,
  buildSyncRevisionPrompt,
} from "./prompts.js";
import { runScanners, hasCriticalFindings, formatFindings } from "./scanners/index.js";
import { runReviewer } from "./reviewer.js";

export type SessionPhase = "extract" | "sync";

export interface RunSyncSessionInputs {
  apiKey: string;
  primaryModel: string;
  reviewModel: string;
  plan: SyncPlan;
  sourceScan: ScanReport | null;
  maxRevisions: number;
  adversarialReview: boolean;
  extraJargonTerms?: string[];
}

export interface RunSyncSessionResult {
  status: "clean" | "exhausted-revisions" | "agent-error";
  phase: SessionPhase;
  remainingFindings: Finding[];
  iterations: number;
  agentId?: string;
  lastRunId?: string;
  errorMessage?: string;
}

export async function runSyncSession(
  inputs: RunSyncSessionInputs,
): Promise<RunSyncSessionResult> {
  if (inputs.plan.phaseAEnabled) {
    const extractResult = await runExtractPhase(inputs);
    if (extractResult.status !== "clean") {
      return { ...extractResult, phase: "extract" };
    }
    console.log(
      chalk.green(
        `[extract] phase clean after ${extractResult.iterations} revision(s); `
          + `proceeding to sync.`,
      ),
    );
  }
  const syncResult = await runSyncPhase(inputs);
  return { ...syncResult, phase: "sync" };
}

interface PhaseResult {
  status: "clean" | "exhausted-revisions" | "agent-error";
  remainingFindings: Finding[];
  iterations: number;
  agentId?: string;
  lastRunId?: string;
  errorMessage?: string;
}

async function runExtractPhase(inputs: RunSyncSessionInputs): Promise<PhaseResult> {
  const { apiKey, primaryModel, reviewModel, plan, sourceScan, maxRevisions, adversarialReview, extraJargonTerms } = inputs;
  if (!plan.extractedPkgAbs || !plan.sourceRepoRoot) {
    throw new Error("runExtractPhase called without extract metadata on the plan.");
  }
  const agent = await Agent.create({
    apiKey,
    model: { id: primaryModel },
    local: { cwd: plan.sourceRepoRoot, settingSources: [] },
  });
  try {
    const initialPrompt = `${EXTRACT_SYSTEM_PROMPT}\n\n---\n\n${buildExtractInitialPrompt({ plan, sourceScan })}`;
    return await scanAndReviseLoop({
      agent,
      apiKey,
      reviewModel,
      plan,
      scanRootAbs: plan.extractedPkgAbs,
      reviewRootAbs: plan.extractedPkgAbs,
      reviewerCwd: plan.sourceRepoRoot,
      initialPrompt,
      buildRevisionPrompt: (findings, iteration) =>
        buildExtractRevisionPrompt({
          plan,
          iteration,
          maxRevisions,
          combinedFindings: findings,
        }),
      maxRevisions,
      adversarialReview,
      extraJargonTerms,
      logPrefix: "[extract]",
    });
  } finally {
    await agent[Symbol.asyncDispose]();
  }
}

async function runSyncPhase(inputs: RunSyncSessionInputs): Promise<PhaseResult> {
  const { apiKey, primaryModel, reviewModel, plan, sourceScan, maxRevisions, adversarialReview, extraJargonTerms } = inputs;
  const agent = await Agent.create({
    apiKey,
    model: { id: primaryModel },
    local: { cwd: plan.targetRepoAbs, settingSources: [] },
  });
  try {
    const jargonHeavy = sourceScan
      ? sourceScan.findings.filter((finding) => finding.source === "jargon").length > 8
      : false;
    const initialPrompt = `${SYNC_SYSTEM_PROMPT}\n\n---\n\n${buildSyncInitialPrompt({ plan, sourceScan, jargonHeavy })}`;
    return await scanAndReviseLoop({
      agent,
      apiKey,
      reviewModel,
      plan,
      scanRootAbs: plan.targetAbs,
      reviewRootAbs: plan.targetAbs,
      reviewerCwd: plan.targetRepoAbs,
      initialPrompt,
      buildRevisionPrompt: (findings, iteration) =>
        buildSyncRevisionPrompt({
          plan,
          iteration,
          maxRevisions,
          combinedFindings: findings,
        }),
      maxRevisions,
      adversarialReview,
      extraJargonTerms,
      logPrefix: "[primary]",
    });
  } finally {
    await agent[Symbol.asyncDispose]();
  }
}

interface ScanAndReviseInputs {
  agent: SDKAgent;
  apiKey: string;
  reviewModel: string;
  plan: SyncPlan;
  scanRootAbs: string;
  reviewRootAbs: string;
  reviewerCwd: string;
  initialPrompt: string;
  buildRevisionPrompt: (findings: Finding[], iteration: number) => string;
  maxRevisions: number;
  adversarialReview: boolean;
  extraJargonTerms?: string[];
  logPrefix: string;
}

async function scanAndReviseLoop({
  agent,
  apiKey,
  reviewModel,
  plan,
  scanRootAbs,
  reviewRootAbs,
  reviewerCwd,
  initialPrompt,
  buildRevisionPrompt,
  maxRevisions,
  adversarialReview,
  extraJargonTerms,
  logPrefix,
}: ScanAndReviseInputs): Promise<PhaseResult> {
  let lastRunId: string | undefined;

  const initialRun = await agent.send(initialPrompt);
  lastRunId = initialRun.id;
  console.log(chalk.dim(`${logPrefix} agent=${agent.agentId} run=${initialRun.id}`));
  await streamAgentText(initialRun, `${logPrefix} `);
  const initialResult = await initialRun.wait();
  if (initialResult.status === "error") {
    return {
      status: "agent-error",
      remainingFindings: [],
      iterations: 0,
      agentId: agent.agentId,
      lastRunId,
      errorMessage: initialResult.result ?? "no error message returned by SDK",
    };
  }

  // Suppress unused-variable noise from the parent plan when we don't reach the
  // SyncPlan-typed branch.
  void plan;

  for (let iteration = 1; iteration <= maxRevisions + 1; iteration += 1) {
    const deterministic = await runScanners({
      rootPath: scanRootAbs,
      jargonSeverity: "critical",
      extraJargonTerms,
    });
    logScanReport(`${logPrefix.replace(/\[|\]/g, "")} deterministic`, deterministic);

    let combinedFindings: Finding[] = deterministic.findings.filter(
      (finding) => finding.severity === "critical",
    );

    if (combinedFindings.length === 0 && adversarialReview) {
      console.log(chalk.dim(`[reviewer] running on model ${reviewModel}`));
      const reviewerFindings = await runReviewer({
        apiKey,
        reviewModel,
        plan,
        reviewRootAbs,
        cwd: reviewerCwd,
      });
      const reviewerCritical = reviewerFindings.filter(
        (finding) => finding.severity === "critical",
      );
      const reviewerWarnings = reviewerFindings.filter(
        (finding) => finding.severity === "warning",
      );
      combinedFindings = reviewerCritical;
      if (reviewerFindings.length > 0) {
        console.log(
          chalk.dim(
            `[reviewer] returned ${reviewerFindings.length} finding(s) `
              + `(critical=${reviewerCritical.length}, warning=${reviewerWarnings.length})`,
          ),
        );
      }
      if (reviewerWarnings.length > 0) {
        console.log(
          chalk.yellow(
            `[reviewer] ${reviewerWarnings.length} non-blocking finding(s) (review manually):`,
          ),
        );
        for (const finding of reviewerWarnings) {
          console.log(
            chalk.yellow(
              `  - ${finding.file}:${finding.line} [${finding.type}] ${finding.message}`,
            ),
          );
        }
      }
    }

    if (combinedFindings.length === 0) {
      return {
        status: "clean",
        remainingFindings: [],
        iterations: iteration - 1,
        agentId: agent.agentId,
        lastRunId,
      };
    }

    if (iteration > maxRevisions) {
      return {
        status: "exhausted-revisions",
        remainingFindings: combinedFindings,
        iterations: maxRevisions,
        agentId: agent.agentId,
        lastRunId,
      };
    }

    const revisionPrompt = buildRevisionPrompt(combinedFindings, iteration);
    const revisionRun = await agent.send(revisionPrompt);
    lastRunId = revisionRun.id;
    console.log(
      chalk.dim(
        `${logPrefix} revision ${iteration}/${maxRevisions} run=${revisionRun.id}`,
      ),
    );
    await streamAgentText(revisionRun, `${logPrefix} revision ${iteration} `);
    const revisionResult = await revisionRun.wait();
    if (revisionResult.status === "error") {
      return {
        status: "agent-error",
        remainingFindings: combinedFindings,
        iterations: iteration,
        agentId: agent.agentId,
        lastRunId,
        errorMessage: revisionResult.result ?? "no error message returned by SDK",
      };
    }
  }

  return {
    status: "exhausted-revisions",
    remainingFindings: [],
    iterations: maxRevisions,
    agentId: agent.agentId,
    lastRunId,
  };
}

interface AssistantBlock {
  type: string;
  text?: unknown;
}

interface AssistantEvent {
  type: string;
  message?: {
    content?: AssistantBlock[];
  };
}

async function streamAgentText(
  run: { stream: () => AsyncIterable<unknown>; supports: (op: "stream") => boolean },
  prefix: string,
): Promise<void> {
  if (!run.supports("stream")) {
    return;
  }
  try {
    for await (const event of run.stream()) {
      const text = extractAssistantText(event);
      if (text) {
        process.stdout.write(chalk.dim(prefix) + text);
      }
    }
  } catch {
    // Stream is best-effort; failures here do not block run.wait().
  }
}

function extractAssistantText(event: unknown): string | null {
  if (!event || typeof event !== "object") return null;
  const typed = event as AssistantEvent;
  if (typed.type !== "assistant") return null;
  const content = typed.message?.content;
  if (!Array.isArray(content)) return null;
  const parts: string[] = [];
  for (const block of content) {
    if (block && block.type === "text" && typeof block.text === "string") {
      parts.push(block.text);
    }
  }
  return parts.length > 0 ? parts.join("") : null;
}

function logScanReport(label: string, report: ScanReport): void {
  if (!hasCriticalFindings(report) && report.findings.length === 0) {
    console.log(chalk.green(`[scan] ${label}: clean (${report.durationMs} ms)`));
    return;
  }
  const counts = report.findings.reduce<Record<string, number>>((acc, finding) => {
    const key = finding.severity;
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});
  console.log(
    chalk.yellow(
      `[scan] ${label}: ${report.findings.length} finding(s) `
        + `(critical=${counts.critical ?? 0}, warning=${counts.warning ?? 0}, ${report.durationMs} ms)`,
    ),
  );
  if (hasCriticalFindings(report)) {
    console.log(formatFindings(report));
  }
}
