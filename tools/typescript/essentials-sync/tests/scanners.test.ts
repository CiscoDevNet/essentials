import { describe, expect, it } from "vitest";
import { generateKeyPairSync } from "node:crypto";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { findJargonTerms, loadJargonConfig } from "../src/jargon-list.js";
import { scanJargon } from "../src/scanners/jargon.js";
import { scanPii } from "../src/scanners/pii.js";
import { scanWithSecretlint } from "../src/scanners/secretlint.js";

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

  it.each([
    ["Deploy it to the AOH dev account.", "aoh"],
    ["Owned by the Sales_AI team.", "sales_ai"],
    ["Run aws-sso first.", "aws-sso"],
    ["Seed the NPI scenarios.", "npi"],
  ])("flags internal names without an override file: %s", (line, term) => {
    expect(findJargonTerms(line, loadJargonConfig()).map((p) => p.term)).toContain(term);
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

  it.each([
    "bob@example.com",
    "bob@example.org",
    "bob@corp.example.com",
    "ada@a.b.example.net",
    "dean@registrar.example.edu",
    "Alice.Smith@Example.COM",
    "Contact bob@example.com.",
  ])("allows %s", async (line) => {
    expect(await emailFindings(line)).toBe(0);
  });

  it.each([
    "bob@corp.example",
    "x@example.invalid",
    "x@host.com",
    "x@example.com.evil.org",
    "x@notexample.com",
    "x@example.io",
  ])("flags %s", async (line) => {
    expect(await emailFindings(line)).toBe(1);
  });
});

describe("secretlint scanner", () => {
  // A key generated per run, in a directory outside this package: secretlint
  // once ran from the package directory and silently skipped such paths.
  it.each([
    ["a directory", (dir: string) => dir],
    ["a single file", (dir: string) => path.join(dir, "key.pem")],
  ])("flags a private key in %s outside the package", async (_label, pickRoot) => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), "secretlint-test-"));
    try {
      const { privateKey } = generateKeyPairSync("ec", { namedCurve: "P-256" });
      const pem = privateKey.export({ type: "pkcs8", format: "pem" }).toString();
      await fs.writeFile(path.join(dir, "key.pem"), pem, "utf8");
      const findings = await scanWithSecretlint(pickRoot(dir));
      expect(findings.map((f) => [f.file, f.term])).toEqual([
        [path.join(dir, "key.pem"), "@secretlint/secretlint-rule-privatekey"],
      ]);
    } finally {
      await fs.rm(dir, { recursive: true, force: true });
    }
  });

  // The JSON report embeds each file's source. Read from a pipe, it was cut
  // off at the 64 KiB pipe buffer on macOS, and the unparseable rest was
  // taken for a clean scan.
  it("flags a private key when the report is larger than a pipe buffer", async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), "secretlint-test-"));
    try {
      await fs.writeFile(path.join(dir, "a-notes.md"), "plain text\n".repeat(20_000), "utf8");
      const { privateKey } = generateKeyPairSync("ec", { namedCurve: "P-256" });
      const pem = privateKey.export({ type: "pkcs8", format: "pem" }).toString();
      await fs.writeFile(path.join(dir, "key.pem"), pem, "utf8");
      const findings = await scanWithSecretlint(dir);
      expect(findings.map((f) => f.term)).toEqual(["@secretlint/secretlint-rule-privatekey"]);
    } finally {
      await fs.rm(dir, { recursive: true, force: true });
    }
  });
});

async function emailFindings(line: string): Promise<number> {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "pii-test-"));
  try {
    await fs.writeFile(path.join(root, "sample.md"), `${line}\n`, "utf8");
    const findings = await scanPii(root, { severity: "critical" });
    return findings.filter((f) => f.term === "email").length;
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
}
