import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { buildReviewerPrompt } from "../src/prompts.ts";
import type { SyncPlan } from "../src/types.ts";

const plan = { targetAbs: "/target/skills/ess/ess-demo" } as SyncPlan;

describe("buildReviewerPrompt", () => {
  it("lists the forbidden terms and the allowed text", () => {
    const prompt = buildReviewerPrompt({ plan, jargonTerms: ["widgetco"], jargonAllowText: ["WidgetCoDevNet"] });

    assert.match(prompt, /FORBIDDEN TERMS[^\n]*\n {2}- widgetco\n/);
    assert.match(prompt, /ALLOWED TEXT[^\n]*\n {2}- WidgetCoDevNet\n/);
  });

  it("leaves out the allowed-text section when there is none", () => {
    const prompt = buildReviewerPrompt({ plan, jargonTerms: ["widgetco"], jargonAllowText: [] });

    assert.doesNotMatch(prompt, /ALLOWED TEXT/);
  });
});
