#!/usr/bin/env node
// Git hook entry point: fails when a commit message, or a line a commit adds,
// contains a forbidden jargon term. The terms come from the jargon file at
// the repo root; with none, the hook fails rather than pass everything.
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";
import {
  DEFAULT_JARGON_FILE,
  findJargonTerms,
  isAllowedPath,
  isJargonFileName,
  loadJargonConfig,
  parseJargonOverrides,
  type JargonAllowList,
  type JargonConfig,
  type JargonOverrides,
} from "./jargon-list.ts";

const SCISSORS_LINE = /^# -+ >8 -+$/;
const MAX_EXCERPT_LENGTH = 120;

export interface JargonHit {
  location: string;
  term: string;
  excerpt: string;
}

export interface AddedLine {
  file: string;
  line: number;
  text: string;
}

export interface CommitChange {
  sha: string;
  message: string;
  addedLines: AddedLine[];
}

// Git hands commit-msg hooks the raw editor buffer: comment lines and, with
// `commit -v`, a diff below the scissors line. Neither is part of the message.
export function readMessageLines(rawMessage: string): string[] {
  const lines: string[] = [];
  for (const line of rawMessage.split(/\r?\n/)) {
    if (SCISSORS_LINE.test(line)) break;
    if (!line.startsWith("#")) lines.push(line);
  }
  return lines;
}

// Parses `git diff --unified=0` output into the lines it adds. File headers are
// only recognized between `diff --git` and the first hunk, so an added line
// that itself starts with "++ " is not mistaken for a header.
export function parseAddedLines(diff: string): AddedLine[] {
  const added: AddedLine[] = [];
  let file: string | null = null;
  let inHeader = false;
  let lineNumber = 0;
  for (const raw of diff.split("\n")) {
    if (raw.startsWith("diff --git ")) {
      inHeader = true;
      file = null;
      continue;
    }
    if (inHeader) {
      if (raw.startsWith("+++ ")) {
        const target = raw.slice(4);
        file = target === "/dev/null" ? null : target.replace(/^b\//, "");
      }
      if (!raw.startsWith("@@")) continue;
      inHeader = false;
    }
    const hunk = /^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(raw);
    if (hunk) {
      lineNumber = Number(hunk[1]);
      continue;
    }
    if (file !== null && raw.startsWith("+")) {
      added.push({ file, line: lineNumber, text: raw.slice(1) });
      lineNumber += 1;
    }
  }
  return added;
}

const RECORD_SEPARATOR = "\x1e";
const MESSAGE_END = "\x1f";

// Parses `git log -p` output produced with GIT_LOG_FORMAT into one entry per
// commit.
export function parseLog(output: string): CommitChange[] {
  const commits: CommitChange[] = [];
  for (const record of output.split(RECORD_SEPARATOR)) {
    const end = record.indexOf(MESSAGE_END);
    if (end === -1) continue;
    const [sha = "", ...messageLines] = record.slice(0, end).split("\n");
    commits.push({
      sha,
      message: messageLines.join("\n"),
      addedLines: parseAddedLines(record.slice(end + 1)),
    });
  }
  return commits;
}

const GIT_LOG_FORMAT = `--format=${RECORD_SEPARATOR}%H%n%B${MESSAGE_END}`;

const excerpt = (text: string): string => {
  const trimmed = text.trim();
  return trimmed.length > MAX_EXCERPT_LENGTH
    ? `${trimmed.slice(0, MAX_EXCERPT_LENGTH)}...`
    : trimmed;
};

export function scanMessage(
  lines: readonly string[],
  locationPrefix: string,
  config: JargonConfig,
  allow: JargonAllowList,
): JargonHit[] {
  const hits: JargonHit[] = [];
  lines.forEach((line, index) => {
    for (const pattern of findJargonTerms(line, config, allow.text)) {
      hits.push({
        location: `${locationPrefix} line ${index + 1}`,
        term: pattern.term,
        excerpt: excerpt(line),
      });
    }
  });
  return hits;
}

export function scanCommits(
  commits: readonly CommitChange[],
  config: JargonConfig,
  allow: JargonAllowList,
): JargonHit[] {
  const hits: JargonHit[] = [];
  for (const commit of commits) {
    const shortSha = commit.sha.slice(0, 7);
    hits.push(
      ...scanMessage(commit.message.split("\n"), `commit ${shortSha} message`, config, allow),
    );
    for (const added of commit.addedLines) {
      if (isAllowedPath(added.file, allow.paths)) continue;
      for (const pattern of findJargonTerms(added.text, config, allow.text)) {
        hits.push({
          location: `commit ${shortSha} ${added.file}:${added.line}`,
          term: pattern.term,
          excerpt: excerpt(added.text),
        });
      }
    }
  }
  return hits;
}

const git = (cwd: string, args: string[]): string =>
  execFileSync("git", args, { cwd, encoding: "utf8", maxBuffer: 256 * 1024 * 1024 });

// The jargon file itself always passes: it is the wordlist, so it lists every
// term.
export function loadRepoOverrides(repoRoot: string, jargonFile = DEFAULT_JARGON_FILE): JargonOverrides {
  const configPath = path.join(repoRoot, jargonFile);
  const overrides = existsSync(configPath)
    ? parseJargonOverrides(JSON.parse(readFileSync(configPath, "utf8")) as unknown)
    : parseJargonOverrides(null);
  return { ...overrides, allow: { ...overrides.allow, paths: [...overrides.allow.paths, jargonFile] } };
}

// Commits the push would publish: everything reachable from `toRef` that no
// remote-tracking ref already has. That covers new branches, fast-forwards,
// and rebases alike, and never rescans history that is already public.
export function listUnpublishedCommits(repoRoot: string, toRef: string): CommitChange[] {
  const output = git(repoRoot, [
    "-c", "core.quotePath=false",
    "log", "-p", "--unified=0", "--no-color", "--no-ext-diff", GIT_LOG_FORMAT,
    toRef, "--not", "--remotes",
  ]);
  return parseLog(output);
}

function formatHits(hits: readonly JargonHit[], jargonFile: string): string {
  const lines = hits.map((hit) => `  ${hit.location}: '${hit.term}' in: ${hit.excerpt}`);
  return [
    `Forbidden jargon found. Reword it, or add an exception to ${jargonFile}:`,
    ...lines,
  ].join("\n");
}

export function main(argv: readonly string[]): number {
  const { values } = parseArgs({
    args: [...argv],
    options: {
      "message-file": { type: "string" },
      "to-ref": { type: "string" },
      "jargon-file": { type: "string", default: DEFAULT_JARGON_FILE },
    },
  });
  const jargonFile = values["jargon-file"];
  if (!isJargonFileName(jargonFile)) {
    console.error(`--jargon-file takes a file name, not a path. Got: ${jargonFile}`);
    return 1;
  }
  const repoRoot = git(process.cwd(), ["rev-parse", "--show-toplevel"]).trim();
  const overrides = loadRepoOverrides(repoRoot, jargonFile);
  const config = loadJargonConfig(overrides.terms);
  if (config.patterns.length === 0) {
    console.error(
      `No jargon terms found in ${path.join(repoRoot, jargonFile)}. List the company's terms `
        + "there, or name a different file with --jargon-file.",
    );
    return 1;
  }

  const messageFile = values["message-file"];
  const hits = messageFile
    ? scanMessage(
        readMessageLines(readFileSync(messageFile, "utf8")),
        "commit message",
        config,
        overrides.allow,
      )
    : scanCommits(
        listUnpublishedCommits(
          repoRoot,
          values["to-ref"] ?? process.env.PRE_COMMIT_TO_REF ?? "HEAD",
        ),
        config,
        overrides.allow,
      );

  if (hits.length === 0) return 0;
  console.error(formatHits(hits, jargonFile));
  return 1;
}

const invokedPath = process.argv[1];
if (invokedPath && import.meta.url === pathToFileURL(path.resolve(invokedPath)).href) {
  process.exitCode = main(process.argv.slice(2));
}
