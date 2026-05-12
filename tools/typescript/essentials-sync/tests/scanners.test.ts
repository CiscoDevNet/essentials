import { describe, expect, it } from "vitest";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { scanJargon } from "../src/scanners/jargon.js";
import { scanPii } from "../src/scanners/pii.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const cleanFixture = path.join(here, "fixtures", "clean-package");
const dirtyFixture = path.join(here, "fixtures", "dirty-package");

describe("jargon scanner", () => {
  it("returns no findings on a clean fixture", async () => {
    const findings = await scanJargon(cleanFixture, { severity: "critical" });
    expect(findings).toEqual([]);
  });

  it("flags cisco terms and hostnames on a dirty fixture", async () => {
    const findings = await scanJargon(dirtyFixture, { severity: "critical" });
    expect(findings.length).toBeGreaterThan(0);
    expect(findings.some((f) => f.term === "cisco")).toBe(true);
    expect(findings.some((f) => f.term === "*.cisco.com")).toBe(true);
  });

  it("respects custom severity", async () => {
    const findings = await scanJargon(dirtyFixture, { severity: "warning" });
    expect(findings.every((f) => f.severity === "warning")).toBe(true);
  });
});

describe("pii scanner", () => {
  it("returns no findings on a clean fixture", async () => {
    const findings = await scanPii(cleanFixture, { severity: "critical" });
    expect(findings).toEqual([]);
  });

  it("flags non-example email addresses on a dirty fixture", async () => {
    const findings = await scanPii(dirtyFixture, { severity: "critical" });
    expect(findings.some((f) => f.term === "email")).toBe(true);
  });
});
