import assert from "node:assert/strict";
import { generateKeyPairSync } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";
import { afterEach, describe, it } from "node:test";
import { findJargonTerms, loadJargonConfig } from "../src/jargon-list.ts";
import { runScanners } from "../src/scanners/index.ts";
import { scanJargon } from "../src/scanners/jargon.ts";
import { scanPii } from "../src/scanners/pii.ts";
import { scanWithSecretlint } from "../src/scanners/secretlint.ts";
import { flaggedEmail, makeFixtureRepo, makeRepo, removeTempDirs } from "./temp-repos.ts";

afterEach(removeTempDirs);

const terms = ["acme-internal", "*.corp.example"];

describe("jargon scanner", () => {
  it("returns no findings on a clean fixture", async () => {
    const findings = await scanJargon(await makeFixtureRepo("clean-package"), { severity: "critical", terms });
    assert.deepEqual(findings, []);
  });

  it("flags configured terms and hostnames on a dirty fixture", async () => {
    const findings = await scanJargon(await makeFixtureRepo("dirty-package"), { severity: "critical", terms });
    assert.ok(findings.some((f) => f.term === "acme-internal" && f.type === "jargon"));
    assert.ok(findings.some((f) => f.term === "*.corp.example" && f.type === "internal-url"));
  });

  it("flags nothing without terms", async () => {
    const findings = await scanJargon(await makeFixtureRepo("dirty-package"), { severity: "critical", terms: [] });
    assert.deepEqual(findings, []);
  });

  const matches: Array<[string, string]> = [
    ["Owned by the ACME-INTERNAL team.", "acme-internal"],
    ["Call api.corp.example first.", "*.corp.example"],
    ["Ask the WidgetCo help desk.", "widgetco"],
    ["Built by the agentic ops group.", "agentic ops"],
  ];
  const config = loadJargonConfig([...terms, "widgetco", "agentic ops"]);
  for (const [line, term] of matches) {
    it(`flags '${term}' in: ${line}`, () => {
      assert.deepEqual(findJargonTerms(line, config).map((p) => p.term), [term]);
    });
  }

  it("matches whole words only", () => {
    assert.deepEqual(findJargonTerms("Widgetcoin and corp.example.org", config), []);
  });

  it("builds no patterns from an empty or blank wordlist", () => {
    assert.deepEqual(loadJargonConfig([]).patterns, []);
    assert.deepEqual(loadJargonConfig(["", "  "]).patterns, []);
  });

  it("respects custom severity", async () => {
    const findings = await scanJargon(await makeFixtureRepo("dirty-package"), { severity: "warning", terms });
    assert.ok(findings.length > 0);
    assert.ok(findings.every((f) => f.severity === "warning"));
  });

  it("skips the jargon file at the scanned root, under any name", async () => {
    const root = await makeRepo("scanners", {
      "jargon.json": JSON.stringify(terms),
      "company-jargon.json": JSON.stringify(terms),
      "docs/jargon.json": JSON.stringify(terms),
      "README.md": "# Clean\n",
    });
    const scan = (jargonFile?: string) =>
      runScanners({
        rootPath: root,
        jargonSeverity: "critical",
        jargonTerms: terms,
        jargonFile,
        skipTrufflehog: true,
        skipSecretlint: true,
      });
    const flaggedFiles = async (jargonFile?: string) =>
      [...new Set((await scan(jargonFile)).findings.map((f) => path.relative(root, f.file)))].sort();

    assert.deepEqual(await flaggedFiles(), ["company-jargon.json", "docs/jargon.json"]);
    assert.deepEqual(await flaggedFiles("company-jargon.json"), ["docs/jargon.json", "jargon.json"]);
  });
});

describe("pii scanner", () => {
  it("returns no findings on a clean fixture", async () => {
    const findings = await scanPii(await makeFixtureRepo("clean-package"), { severity: "critical" });
    assert.deepEqual(findings, []);
  });

  it("skips lock files, which carry upstream maintainers' addresses", async () => {
    const notice = `"deprecated": "Contact ${flaggedEmail("maintainer")}"\n`;
    const root = await makeRepo("pii", { "package-lock.json": notice, "uv.lock": notice, "notes.md": notice });

    const findings = await scanPii(root, { severity: "critical" });

    assert.deepEqual(findings.map((f) => path.basename(f.file)), ["notes.md"]);
  });

  const allowed = [
    "bob@example.com",
    "bob@example.org",
    "bob@corp.example.com",
    "ada@a.b.example.net",
    "dean@registrar.example.edu",
    "Alice.Smith@Example.COM",
    "Contact bob@example.com.",
    "bob@corp.example",
    "test@example.invalid",
    "ci@runner.test",
    "Ops@Host.INVALID",
  ];
  for (const line of allowed) {
    it(`allows ${line}`, async () => {
      assert.equal(await emailFindings(line), 0);
    });
  }

  const flagged = [
    "host.com",
    "example.com.evil.org",
    "notexample.com",
    "example.io",
    "test.com",
    "example.invalid.com",
    "invalid.io",
  ].map((domain) => ["x", domain].join("@"));
  for (const line of flagged) {
    it(`flags ${line}`, async () => {
      assert.equal(await emailFindings(line), 1);
    });
  }
});

describe("secretlint scanner", () => {
  // A key generated per run, in a repo outside this skill: secretlint once
  // ran from the package directory and silently skipped such paths.
  const roots: Array<[string, (dir: string) => string]> = [
    ["a directory", (dir) => dir],
    ["a single file", (dir) => path.join(dir, "key.pem")],
  ];
  for (const [label, pickRoot] of roots) {
    it(`flags a private key in ${label} outside the skill`, async () => {
      const dir = await makeRepo("secretlint");
      await fs.writeFile(path.join(dir, "key.pem"), privateKeyPem(), "utf8");

      const findings = await scanWithSecretlint(pickRoot(dir));

      assert.deepEqual(
        findings.map((f) => [f.file, f.term]),
        [[path.join(dir, "key.pem"), "@secretlint/secretlint-rule-privatekey"]],
      );
    });
  }

  // The JSON report embeds each file's source. Read from a pipe, it was cut
  // off at the 64 KiB pipe buffer on macOS, and the unparseable rest was
  // taken for a clean scan.
  it("flags a private key when the report is larger than a pipe buffer", async () => {
    const dir = await makeRepo("secretlint");
    await fs.writeFile(path.join(dir, "a-notes.md"), "plain text\n".repeat(20_000), "utf8");
    await fs.writeFile(path.join(dir, "key.pem"), privateKeyPem(), "utf8");

    const findings = await scanWithSecretlint(dir);

    assert.deepEqual(findings.map((f) => f.term), ["@secretlint/secretlint-rule-privatekey"]);
  });
});

function privateKeyPem(): string {
  const { privateKey } = generateKeyPairSync("ec", { namedCurve: "P-256" });
  return privateKey.export({ type: "pkcs8", format: "pem" }).toString();
}

async function emailFindings(line: string): Promise<number> {
  const root = await makeRepo("pii", { "sample.md": `${line}\n` });
  const findings = await scanPii(root, { severity: "critical" });
  return findings.filter((f) => f.term === "email").length;
}
