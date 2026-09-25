import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  listUnpublishedCommits,
  parseAddedLines,
  readMessageLines,
  scanCommits,
  scanMessage,
} from "../src/jargon-check.js";
import {
  findJargonTerms,
  isAllowedPath,
  loadJargonConfig,
  parseJargonOverrides,
} from "../src/jargon-list.js";

// Made-up terms, so this file needs no exception in the repo's allow list.
const config = loadJargonConfig(["codename", "*.corp.example"]);
const noAllow = { paths: [], text: [] };

describe("parseJargonOverrides", () => {
  it("accepts a flat array of terms", () => {
    expect(parseJargonOverrides(["codename"])).toEqual({
      terms: ["codename"],
      allow: { paths: [], text: [] },
    });
  });

  it("reads terms and both allow lists, dropping non-strings", () => {
    const overrides = parseJargonOverrides({
      terms: ["codename", 7],
      allow: { paths: ["docs/**"], text: ["docs.corp.example", null] },
    });
    expect(overrides).toEqual({
      terms: ["codename"],
      allow: { paths: ["docs/**"], text: ["docs.corp.example"] },
    });
  });

  it("treats a missing or malformed file as empty", () => {
    expect(parseJargonOverrides(null)).toEqual({ terms: [], allow: { paths: [], text: [] } });
    expect(parseJargonOverrides({ allow: "docs/**" }).allow).toEqual({ paths: [], text: [] });
  });
});

describe("isAllowedPath", () => {
  it("matches exact paths and ** at any depth", () => {
    expect(isAllowedPath("src/jargon-list.ts", ["src/jargon-list.ts"])).toBe(true);
    expect(isAllowedPath("tests/fixtures/dirty/src/client.py", ["tests/**"])).toBe(true);
    expect(isAllowedPath("pkg/a/b/notes.md", ["**/*.md"])).toBe(true);
  });

  it("keeps a single * within one directory", () => {
    expect(isAllowedPath("docs/nested/readme.md", ["docs/*.md"])).toBe(false);
    expect(isAllowedPath("src/jargon-list.ts.bak", ["src/jargon-list.ts"])).toBe(false);
  });
});

describe("findJargonTerms", () => {
  it("blanks allowed text but still flags a forbidden term on the same line", () => {
    const line = "see https://docs.corp.example and https://auth.corp.example";
    const terms = findJargonTerms(line, config, ["docs.corp.example"]).map((p) => p.term);
    expect(terms).toEqual(["*.corp.example"]);
    expect(findJargonTerms("see https://docs.corp.example", config, ["docs.corp.example"])).toEqual([]);
  });

  it("matches whole words only, so a longer name that starts with a term passes", () => {
    expect(findJargonTerms("github.com/CodenameDevNet/essentials", config)).toEqual([]);
    expect(findJargonTerms("the codename-auth tool", config).map((p) => p.term)).toEqual(["codename"]);
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
    expect(readMessageLines(raw)).toEqual(["feat: add a thing", "", "Body text."]);
  });
});

describe("scanMessage", () => {
  it("reports the term and line of a forbidden word", () => {
    const hits = scanMessage(["fix: tidy", "", "Matches the codename setup."], "msg", config, noAllow);
    expect(hits).toEqual([
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
    expect(parseAddedLines(diff)).toEqual([
      { file: "app.py", line: 4, text: "first = 1" },
      { file: "app.py", line: 5, text: "++ second" },
    ]);
  });
});

describe("scanCommits against a real repository", () => {
  let repo = "";

  afterEach(() => {
    if (repo) rmSync(repo, { recursive: true, force: true });
  });

  const git = (...args: string[]) =>
    execFileSync("git", args, { cwd: repo, encoding: "utf8" });

  const commit = (message: string, files: Record<string, string>) => {
    for (const [file, content] of Object.entries(files)) {
      mkdirSync(path.dirname(path.join(repo, file)), { recursive: true });
      writeFileSync(path.join(repo, file), content);
    }
    git("add", "-A");
    git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "--no-verify", "-m", message);
  };

  it("flags messages and added lines, honoring allowed paths and text", () => {
    repo = mkdtempSync(path.join(tmpdir(), "jargon-check-"));
    git("init", "-q");
    commit("chore: start", { "README.md": "hello\n" });
    commit("chore: align with codename", {
      "src/client.py": 'HOST = "auth.corp.example"\nDOCS = "https://docs.corp.example"\n',
      "tests/fixtures/dirty.py": 'HOST = "auth.corp.example"\n',
    });

    const allow = { paths: ["tests/**"], text: ["docs.corp.example"] };
    const hits = scanCommits(listUnpublishedCommits(repo, "HEAD"), config, allow);
    const summary = hits.map((hit) => `${hit.location.replace(/[0-9a-f]{7}/, "SHA")} ${hit.term}`);

    expect(summary).toEqual([
      "commit SHA message line 1 codename",
      "commit SHA src/client.py:1 *.corp.example",
    ]);
  });
});
