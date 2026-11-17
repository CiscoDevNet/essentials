import assert from "node:assert/strict";
import { generateKeyPairSync } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";
import { afterEach, describe, it } from "node:test";
import {
  COMPANY_MESSAGE,
  DEFAULT_JARGON_PATTERNS,
  findJargonTerms,
  loadJargonConfig,
} from "../src/jargon-list.ts";
import { scanJargon } from "../src/scanners/jargon.ts";
import { scanPii } from "../src/scanners/pii.ts";
import { scanWithSecretlint } from "../src/scanners/secretlint.ts";
import { makeFixtureRepo, makeRepo, removeTempDirs } from "./temp-repos.ts";

afterEach(removeTempDirs);

describe("jargon scanner", () => {
  it("returns no findings on a clean fixture", async () => {
    const findings = await scanJargon(await makeFixtureRepo("clean-package"), { severity: "critical" });
    assert.deepEqual(findings, []);
  });

  it("flags company terms and hostnames on a dirty fixture", async () => {
    const findings = await scanJargon(await makeFixtureRepo("dirty-package"), { severity: "critical" });
    assert.ok(findings.some((f) => f.type === "jargon"));
    assert.ok(findings.some((f) => f.type === "internal-url"));
  });

  it("flags every default term in a sentence without an override file", () => {
    const config = loadJargonConfig();
    for (const { term } of DEFAULT_JARGON_PATTERNS) {
      const word = term.startsWith("*.") ? `api.${term.slice(2)}` : term.toUpperCase();
      assert.ok(findJargonTerms(`Ask the ${word} team.`, config).some((p) => p.term === term), term);
    }
  });

  it("gives every default pattern the same generic message", () => {
    assert.deepEqual(new Set(DEFAULT_JARGON_PATTERNS.map((p) => p.message)), new Set([COMPANY_MESSAGE]));
  });

  it("respects custom severity", async () => {
    const findings = await scanJargon(await makeFixtureRepo("dirty-package"), { severity: "warning" });
    assert.ok(findings.every((f) => f.severity === "warning"));
  });
});

describe("pii scanner", () => {
  it("returns no findings on a clean fixture", async () => {
    const findings = await scanPii(await makeFixtureRepo("clean-package"), { severity: "critical" });
    assert.deepEqual(findings, []);
  });

  it("flags non-example email addresses on a dirty fixture", async () => {
    const findings = await scanPii(await makeFixtureRepo("dirty-package"), { severity: "critical" });
    assert.ok(findings.some((f) => f.term === "email"));
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
    "x@host.com",
    "x@example.com.evil.org",
    "x@notexample.com",
    "x@example.io",
    "x@test.com",
    "x@example.invalid.com",
    "x@invalid.io",
  ];
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
