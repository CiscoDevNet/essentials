import { parseArgs } from "node:util";
import { rethrowAsUsageError } from "./args.ts";
import { envFileCandidates } from "./env.ts";
import { run } from "./exec.ts";
import { MIN_NODE_MAJOR, PROGRAM_NAME } from "./program.ts";
import { isSdkInstalled, sdkInstallDirectory } from "./sdk.ts";
import { style } from "./style.ts";

export const PREFLIGHT_HELP = `Usage: ${PROGRAM_NAME} preflight

Check what sync needs: Node ${MIN_NODE_MAJOR} or later, git, npm, and a
CURSOR_API_KEY. A missing trufflehog is a warning; that scanner is skipped.
Exits 1 if any check fails.`;

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

export async function runPreflightCommand(argv: string[]): Promise<number> {
  try {
    const { values } = parseArgs({ args: argv, options: { help: { type: "boolean", short: "h" } } });
    if (values.help) {
      console.log(PREFLIGHT_HELP);
      return 0;
    }
  } catch (error) {
    rethrowAsUsageError(error);
  }

  const checks = [
    checkNode(),
    await checkTool("git", ["--version"], "git is not installed", "fail"),
    await checkTool("npm", ["--version"], "npm is not installed (needed for secretlint and the Cursor SDK)", "fail"),
    checkApiKey(),
    await checkSdk(),
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

async function checkSdk(): Promise<Check> {
  const directory = await sdkInstallDirectory();
  return (await isSdkInstalled())
    ? { level: "ok", message: `@cursor/sdk installed in ${directory}` }
    : { level: "info", message: `@cursor/sdk installs into ${directory} on the first sync` };
}
