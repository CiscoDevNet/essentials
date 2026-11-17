import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { canFastCopy } from "../src/agent.ts";
import type { RunSyncSessionInputs } from "../src/agent.ts";
import type { Finding, ScanReport, SyncPlan } from "../src/types.ts";

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
  term: "codename",
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
    assert.equal(canFastCopy(inputs()), true);
  });

  it("refuses when the source scan found anything, even a warning", () => {
    assert.equal(canFastCopy(inputs({ sourceScan: scan([jargonFinding]) })), false);
  });

  // Without a scan there is no evidence the source is generic, so the agent has
  // to do the work.
  it("refuses when the source scan was skipped", () => {
    assert.equal(canFastCopy(inputs({ sourceScan: null })), false);
  });

  // Phase A output is authored by the agent; there is no pre-existing tree.
  it("refuses in extract mode", () => {
    assert.equal(canFastCopy(inputs({ plan: { ...plan, phaseAEnabled: true } })), false);
  });

  it("refuses when the operator passed --no-fast-copy", () => {
    assert.equal(canFastCopy(inputs({ fastCopy: false })), false);
  });
});
