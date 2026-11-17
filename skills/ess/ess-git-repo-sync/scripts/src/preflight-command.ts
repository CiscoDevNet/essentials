import path from "node:path";
import { parseArgs } from "node:util";
import { JARGON_FILE_OPTION, parseJargonFileName, rethrowAsUsageError } from "./args.ts";
import { envFileCandidates } from "./env.ts";
import { findGitRoot } from "./ess-items.ts";
import { run } from "./exec.ts";
import { DEFAULT_JARGON_FILE } from "./jargon-list.ts";
import { loadJargonTerms } from "./jargon-overrides.ts";
import { MIN_NODE_MAJOR, PROGRAM_NAME } from "./program.ts";
import { isSdkInstalled, sdkInstallDirectory } from "./sdk.ts";
import { style } from "./style.ts";

export const PREFLIGHT_HELP = `Usage: ${PROGRAM_NAME} preflight [--jargon-file <name>]

Check what sync needs: Node ${MIN_NODE_MAJOR} or later, git, npm, and a
CURSOR_API_KEY. Also reports the current repo (the default sync target) and
its jargon file. A missing trufflehog is a warning; that scanner is skipped.
Exits 1 if any check fails.

Options:
  --jargon-file <name>  Name of the jargon file (default: ${DEFAULT_JARGON_FILE})
  -h, --help            Show this help`;

type CheckLevel = "ok" | "warn" | "fail" | "info";

interface Check {
  level: CheckLevel;
  message: string;
}

const LABELS: Record<CheckLevel, string> = {
  ok: style.green("ok   "),
  warn: style.yellow("WARN "),
  fail: style.red("FAIL "),
  info: style.dim("info "),
};

export async function runPreflightCommand(argv: string[], cwd = process.cwd()): Promise<number> {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      options: { "jargon-file": JARGON_FILE_OPTION, help: { type: "boolean", short: "h" } },
    });
  } catch (error) {
    rethrowAsUsageError(error);
  }
  if (parsed.values.help) {
    console.log(PREFLIGHT_HELP);
    return 0;
  }
  const jargonFile = parseJargonFileName(parsed.values["jargon-file"]);

  const checks = [
    checkNode(),
    await checkTool("git", ["--version"], "git is not installed", "fail"),
    await checkTool("npm", ["--version"], "npm is not installed (needed for secretlint and the Cursor SDK)", "fail"),
    checkApiKey(),
    await checkSdk(),
    ...(await checkCurrentRepo(cwd, jargonFile)),
    await checkTool(
      "trufflehog",
      ["--version"],
      "trufflehog is not installed; that scanner will be skipped (brew install trufflehog)",
      "warn",
    ),
  ];
  for (const check of checks) {
    console.log(`${LABELS[check.level]} ${check.message}`);
  }
  return checks.some((check) => check.level === "fail") ? 1 : 0;
}

function checkNode(): Check {
  const major = Number(process.versions.node.split(".")[0]);
  return major >= MIN_NODE_MAJOR
    ? { level: "ok", message: `node ${process.version}` }
    : { level: "fail", message: `node ${process.version} is too old (need ${MIN_NODE_MAJOR} or later)` };
}

async function checkTool(
  binary: string,
  args: string[],
  missingMessage: string,
  missingLevel: CheckLevel,
): Promise<Check> {
  try {
    const result = await run(binary, args);
    if (result.exitCode === 0) {
      const version = (result.stdout || result.stderr).trim().split("\n")[0];
      return { level: "ok", message: `${binary} ${version}` };
    }
  } catch {
    // Not installed.
  }
  return { level: missingLevel, message: missingMessage };
}

// The CLI loads the .env files before dispatching, so an exported key and
// one from a .env look the same here.
function checkApiKey(): Check {
  if (process.env.CURSOR_API_KEY) {
    return { level: "ok", message: "CURSOR_API_KEY is set" };
  }
  return {
    level: "fail",
    message: `CURSOR_API_KEY is not set, and no .env provides it (looked in ${envFileCandidates().join(", ")})`,
  };
}

// Only warnings: the source repo or the item may still supply the terms,
// and sync fails closed if none does.
async function checkCurrentRepo(cwd: string, jargonFile: string): Promise<Check[]> {
  const repo = await findGitRoot(cwd);
  if (!repo) {
    return [{ level: "warn", message: `${cwd} is not in a git repo; sync needs --target-repo` }];
  }
  const checks: Check[] = [{ level: "ok", message: `default sync target: ${repo}` }];
  try {
    const { terms } = await loadJargonTerms([repo], jargonFile);
    checks.push(
      terms.length > 0
        ? { level: "ok", message: `${terms.length} jargon term(s) in ${path.join(repo, jargonFile)}` }
        : {
            level: "warn",
            message: `no jargon terms in ${path.join(repo, jargonFile)}; sync and scan fail unless `
              + "the source repo or the item lists them",
          },
    );
  } catch (error) {
    checks.push({ level: "fail", message: (error as Error).message });
  }
  return checks;
}

async function checkSdk(): Promise<Check> {
  const directory = await sdkInstallDirectory();
  return (await isSdkInstalled())
    ? { level: "ok", message: `@cursor/sdk installed in ${directory}` }
    : { level: "info", message: `@cursor/sdk installs into ${directory} on the first sync` };
}
