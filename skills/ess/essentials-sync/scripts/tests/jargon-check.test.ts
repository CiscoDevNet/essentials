import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { afterEach, describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import {
  listUnpublishedCommits,
  loadRepoOverrides,
  parseAddedLines,
  readMessageLines,
  scanCommits,
  scanMessage,
} from "../src/jargon-check.ts";
import {
  findJargonTerms,
  isAllowedPath,
  loadJargonConfig,
  parseJargonOverrides,
} from "../src/jargon-list.ts";
import { git, makeRepo, removeTempDirs } from "./temp-repos.ts";

const JARGON_CHECK = fileURLToPath(new URL("../src/jargon-check.ts", import.meta.url));

// Made-up terms, so this file needs no exception in the repo's allow list.
const config = loadJargonConfig(["codename", "*.corp.example"]);
const noAllow = { paths: [], text: [] };

describe("parseJargonOverrides", () => {
  it("accepts a flat array of terms", () => {
    assert.deepEqual(parseJargonOverrides(["codename"]), {
      terms: ["codename"],
      allow: { paths: [], text: [] },
    });
  });

  it("reads terms and both allow lists, dropping non-strings", () => {
    const overrides = parseJargonOverrides({
      terms: ["codename", 7],
      allow: { paths: ["docs/**"], text: ["docs.corp.example", null] },
    });
    assert.deepEqual(overrides, {
      terms: ["codename"],
      allow: { paths: ["docs/**"], text: ["docs.corp.example"] },
    });
  });

  it("treats a missing or malformed file as empty", () => {
    assert.deepEqual(parseJargonOverrides(null), { terms: [], allow: { paths: [], text: [] } });
    assert.deepEqual(parseJargonOverrides({ allow: "docs/**" }).allow, { paths: [], text: [] });
  });
});

describe("isAllowedPath", () => {
  it("matches exact paths and ** at any depth", () => {
    assert.equal(isAllowedPath("src/jargon-list.ts", ["src/jargon-list.ts"]), true);
    assert.equal(isAllowedPath("tests/fixtures/dirty/src/client.py", ["tests/**"]), true);
    assert.equal(isAllowedPath("pkg/a/b/notes.md", ["**/*.md"]), true);
  });

  it("keeps a single * within one directory", () => {
    assert.equal(isAllowedPath("docs/nested/readme.md", ["docs/*.md"]), false);
    assert.equal(isAllowedPath("src/jargon-list.ts.bak", ["src/jargon-list.ts"]), false);
  });
});

describe("findJargonTerms", () => {
  it("blanks allowed text but still flags a forbidden term on the same line", () => {
    const line = "see https://docs.corp.example and https://auth.corp.example";
    const terms = findJargonTerms(line, config, ["docs.corp.example"]).map((p) => p.term);
    assert.deepEqual(terms, ["*.corp.example"]);
    assert.deepEqual(findJargonTerms("see https://docs.corp.example", config, ["docs.corp.example"]), []);
  });

  it("matches whole words only, so a longer name that starts with a term passes", () => {
    assert.deepEqual(findJargonTerms("github.com/CodenameDevNet/essentials", config), []);
    assert.deepEqual(findJargonTerms("the codename-auth tool", config).map((p) => p.term), ["codename"]);
  });
});

describe("readMessageLines", () => {
  it("drops comment lines and everything below the scissors line", () => {
    const raw = [
      "feat: add a thing",
      "# Please enter the commit message",
      "",
      "Body text.",
      "# ------------------------ >8 ------------------------",
      "+ added codename line in the verbose diff",
    ].join("\n");
    assert.deepEqual(readMessageLines(raw), ["feat: add a thing", "", "Body text."]);
  });
});

describe("scanMessage", () => {
  it("reports the term and line of a forbidden word", () => {
    const hits = scanMessage(["fix: tidy", "", "Matches the codename setup."], "msg", config, noAllow);
    assert.deepEqual(hits, [
      { location: "msg line 3", term: "codename", excerpt: "Matches the codename setup." },
    ]);
  });
});

describe("parseAddedLines", () => {
  it("returns added lines with their new-file line numbers", () => {
    const diff = [
      "diff --git a/app.py b/app.py",
      "index 1111111..2222222 100644",
      "--- a/app.py",
      "+++ b/app.py",
      "@@ -3,0 +4,2 @@ def main():",
      "+first = 1",
      "+++ second",
      "diff --git a/gone.py b/gone.py",
      "deleted file mode 100644",
      "--- a/gone.py",
      "+++ /dev/null",
      "@@ -1 +0,0 @@",
      "-removed",
    ].join("\n");
    assert.deepEqual(parseAddedLines(diff), [
      { file: "app.py", line: 4, text: "first = 1" },
      { file: "app.py", line: 5, text: "++ second" },
    ]);
  });
});

function commitTo(repo: string, message: string, files: Record<string, string>): void {
  for (const [file, content] of Object.entries(files)) {
    mkdirSync(path.dirname(path.join(repo, file)), { recursive: true });
    writeFileSync(path.join(repo, file), content);
  }
  git(repo, "add", "-A");
  git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "--no-verify", "-m", message);
}

describe("scanCommits against a real repository", () => {
  afterEach(removeTempDirs);

  it("flags messages and added lines, honoring allowed paths and text", async () => {
    const repo = await makeRepo("jargon-check");
    const commit = (message: string, files: Record<string, string>) => commitTo(repo, message, files);

    commit("chore: start", { "README.md": "hello\n" });
    commit("chore: align with codename", {
      "src/client.py": 'HOST = "auth.corp.example"\nDOCS = "https://docs.corp.example"\n',
      "tests/fixtures/dirty.py": 'HOST = "auth.corp.example"\n',
    });

    const allow = { paths: ["tests/**"], text: ["docs.corp.example"] };
    const hits = scanCommits(listUnpublishedCommits(repo, "HEAD"), config, allow);
    const summary = hits.map((hit) => `${hit.location.replace(/[0-9a-f]{7}/, "SHA")} ${hit.term}`);

    assert.deepEqual(summary, [
      "commit SHA message line 1 codename",
      "commit SHA src/client.py:1 *.corp.example",
    ]);
  });
});

describe("the jargon-check hook", () => {
  afterEach(removeTempDirs);

  const runHook = (repo: string, args: string[] = []) =>
    spawnSync(process.execPath, [JARGON_CHECK, "--to-ref", "HEAD", ...args], { cwd: repo, encoding: "utf8" });

  it("fails closed when the repo lists no terms", async () => {
    const repo = await makeRepo("jargon-hook");
    commitTo(repo, "chore: start", { "README.md": "hello\n" });

    const result = runHook(repo);

    assert.equal(result.status, 1);
    assert.match(result.stderr, /No jargon terms found in .*jargon\.json/);
  });

  it("never flags the wordlist file itself, under any name", async () => {
    const repo = await makeRepo("jargon-hook");
    commitTo(repo, "chore: start", {
      "jargon.json": JSON.stringify(["codename"]),
      "company-jargon.json": JSON.stringify(["codename"]),
      "README.md": "hello\n",
    });

    const flagged = (args?: string[]) =>
      [...runHook(repo, args).stderr.matchAll(/ (\S+):1: 'codename'/g)].map((match) => match[1]);

    assert.equal(runHook(repo).status, 1);
    assert.deepEqual(flagged(), ["company-jargon.json"]);
    assert.deepEqual(flagged(["--jargon-file", "company-jargon.json"]), ["jargon.json"]);
  });

  it("passes a clean history", async () => {
    const repo = await makeRepo("jargon-hook");
    commitTo(repo, "chore: start", { "jargon.json": JSON.stringify(["codename"]), "README.md": "hello\n" });

    const result = runHook(repo);

    assert.equal(result.status, 0, result.stderr);
  });

  it("adds the wordlist file to the allowed paths", () => {
    assert.deepEqual(loadRepoOverrides("/nonexistent", "company-jargon.json").allow.paths, ["company-jargon.json"]);
  });
});
