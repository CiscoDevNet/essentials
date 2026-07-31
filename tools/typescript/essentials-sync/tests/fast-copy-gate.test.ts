import { describe, expect, it } from "vitest";
import { canFastCopy } from "../src/agent.js";
import type { RunSyncSessionInputs } from "../src/agent.js";
import type { Finding, ScanReport, SyncPlan } from "../src/types.js";

const plan: SyncPlan = {
  mode: "COPY",
  sourceAbs: "/src/skills/ess/demo",
  targetRepoAbs: "/target",
  targetPathRel: "skills/ess/demo",
  targetAbs: "/target/skills/ess/demo",
  phaseAEnabled: false,
};

function scan(findings: Finding[]): ScanReport {
  return { findings, scannedPaths: ["/src/skills/ess/demo"], durationMs: 1 };
}

const jargonFinding: Finding = {
  file: "SKILL.md",
  line: 3,
  type: "jargon",
  severity: "warning",
  source: "jargon",
  message: "company term",
  term: "cisco",
};

function inputs(overrides: Partial<RunSyncSessionInputs> = {}): RunSyncSessionInputs {
  return {
    apiKey: "test",
    primaryModel: "primary",
    reviewModel: "review",
    plan,
    sourceScan: scan([]),
    maxRevisions: 3,
    adversarialReview: true,
    fastCopy: true,
    ...overrides,
  };
}

describe("canFastCopy", () => {
  it("allows the copy when the source scan is completely clean", () => {
    expect(canFastCopy(inputs())).toBe(true);
  });

  it("refuses when the source scan found anything, even a warning", () => {
    expect(canFastCopy(inputs({ sourceScan: scan([jargonFinding]) }))).toBe(false);
  });

  // Without a scan there is no evidence the source is generic, so the agent has
  // to do the work.
  it("refuses when the source scan was skipped", () => {
    expect(canFastCopy(inputs({ sourceScan: null }))).toBe(false);
  });

  // Phase A output is authored by the agent; there is no pre-existing tree.
  it("refuses in extract mode", () => {
    expect(canFastCopy(inputs({ plan: { ...plan, phaseAEnabled: true } }))).toBe(false);
  });

  it("refuses when the operator passed --no-fast-copy", () => {
    expect(canFastCopy(inputs({ fastCopy: false }))).toBe(false);
  });
});
