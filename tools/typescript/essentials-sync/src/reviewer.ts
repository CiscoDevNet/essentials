import { Agent } from "@cursor/sdk";
import type { Finding, SyncPlan } from "./types.js";
import { buildReviewerPrompt } from "./prompts.js";

export interface RunReviewerInputs {
  apiKey: string;
  reviewModel: string;
  plan: SyncPlan;
  // Path the reviewer should inspect. Defaults to plan.targetAbs (sync phase);
  // during the extract phase callers pass the extracted package path so the
  // reviewer audits the new shared library rather than the essentials target.
  reviewRootAbs?: string;
  // Working directory for the reviewer agent. Defaults to plan.targetRepoAbs.
  // During the extract phase callers pass plan.sourceRepoRoot (the private
  // source repo) so the reviewer can read files inside the extracted package
  // directly.
  cwd?: string;
}

interface ReviewerJsonResult {
  findings?: Array<{
    file?: unknown;
    line?: unknown;
    type?: unknown;
    severity?: unknown;
    message?: unknown;
  }>;
}

export async function runReviewer({
  apiKey,
  reviewModel,
  plan,
  reviewRootAbs,
  cwd,
}: RunReviewerInputs): Promise<Finding[]> {
  const effectiveReviewRoot = reviewRootAbs ?? plan.targetAbs;
  const effectiveCwd = cwd ?? plan.targetRepoAbs;
  const prompt = buildReviewerPrompt({ plan, reviewRootAbs: effectiveReviewRoot });
  const result = await Agent.prompt(prompt, {
    apiKey,
    model: { id: reviewModel },
    local: { cwd: effectiveCwd, settingSources: [] },
  });

  const rawText = extractText(result);
  const json = extractJsonObject(rawText);
  if (!json) {
    return [
      {
        file: effectiveReviewRoot,
        line: 1,
        type: "other",
        severity: "warning",
        source: "reviewer",
        message: `Reviewer output could not be parsed as JSON. Raw: ${truncate(rawText, 200)}`,
      },
    ];
  }

  return convertToFindings(json);
}

function extractText(result: unknown): string {
  if (typeof result === "string") return result;
  if (result && typeof result === "object") {
    const candidate = (result as { result?: unknown }).result;
    if (typeof candidate === "string") return candidate;
    const message = (result as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return JSON.stringify(result);
}

function extractJsonObject(text: string): ReviewerJsonResult | null {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const candidate = (fenced?.[1] ?? text).trim();
  const firstBrace = candidate.indexOf("{");
  const lastBrace = candidate.lastIndexOf("}");
  if (firstBrace === -1 || lastBrace === -1 || lastBrace <= firstBrace) {
    return null;
  }
  const sliced = candidate.slice(firstBrace, lastBrace + 1);
  try {
    return JSON.parse(sliced) as ReviewerJsonResult;
  } catch {
    return null;
  }
}

function convertToFindings(json: ReviewerJsonResult): Finding[] {
  const items = Array.isArray(json.findings) ? json.findings : [];
  const findings: Finding[] = [];
  for (const item of items) {
    const file = typeof item.file === "string" ? item.file : "<unknown>";
    const line = typeof item.line === "number" && Number.isFinite(item.line)
      ? Math.max(1, Math.floor(item.line))
      : 1;
    const severity = item.severity === "warning" ? "warning" : "critical";
    const type = normalizeType(item.type);
    const message = typeof item.message === "string" ? item.message : "Reviewer flagged this location.";
    findings.push({
      file,
      line,
      type,
      severity,
      source: "reviewer",
      message,
    });
  }
  return findings;
}

function normalizeType(raw: unknown): Finding["type"] {
  const known: Finding["type"][] = [
    "secret",
    "pii",
    "jargon",
    "internal-url",
    "internal-reference",
    "other",
  ];
  if (typeof raw === "string") {
    const lower = raw.toLowerCase();
    for (const candidate of known) {
      if (candidate === lower) return candidate;
    }
  }
  return "other";
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max)}...`;
}
