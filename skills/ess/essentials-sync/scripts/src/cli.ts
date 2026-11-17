#!/usr/bin/env node
import { parseArgs } from "node:util";
import { rethrowAsUsageError, UsageError } from "./args.ts";
import { loadEnvFiles } from "./env.ts";
import { listAvailableModels } from "./model-resolver.ts";
import { runPreflightCommand } from "./preflight-command.ts";
import { PROGRAM_NAME } from "./program.ts";
import { runScanCommand } from "./scan-command.ts";
import { runStatusCommand } from "./status-command.ts";
import { style } from "./style.ts";
import { runSyncCommand } from "./sync-command.ts";

const HELP = `Usage: ${PROGRAM_NAME} <command> [options]

Sync an item from a source repo into a target repo, with deterministic
scanners (secrets, jargon, PII) and an adversarial LLM reviewer in between.

Commands:
  preflight  Check the tools and credentials sync needs
  sync       Extract and sync an item (writes; confirms first, or --dry-run)
  scan       Run the deterministic scanners on paths (read-only)
  status     Compare the ess-* items in two repos (read-only)
  models     List the model IDs available to CURSOR_API_KEY (read-only)

Run '${PROGRAM_NAME} <command> --help' for a command's options.`;

const MODELS_HELP = `Usage: ${PROGRAM_NAME} models

Print the model IDs available to CURSOR_API_KEY, one per line.`;

const COMMANDS: Record<string, (argv: string[]) => Promise<number>> = {
  preflight: runPreflightCommand,
  sync: (argv) => runSyncCommand(argv),
  scan: runScanCommand,
  status: runStatusCommand,
  models: runModelsCommand,
};

// Only the commands that talk to Cursor read the .env files.
const NEEDS_ENV = new Set(["preflight", "sync", "models"]);

async function runModelsCommand(argv: string[]): Promise<number> {
  try {
    const { values } = parseArgs({ args: argv, options: { help: { type: "boolean", short: "h" } } });
    if (values.help) {
      console.log(MODELS_HELP);
      return 0;
    }
  } catch (error) {
    rethrowAsUsageError(error);
  }
  const apiKey = process.env.CURSOR_API_KEY;
  if (!apiKey) {
    throw new Error("CURSOR_API_KEY is not set. Export it or add it to a .env file.");
  }
  const models = await listAvailableModels(apiKey);
  if (models.length === 0) {
    console.log("No models returned from Cursor.models.list().");
  }
  for (const id of models) {
    console.log(id);
  }
  return 0;
}

async function main(argv: string[]): Promise<number> {
  const [name, ...rest] = argv;
  if (name === undefined || name === "help" || name === "--help" || name === "-h") {
    console.log(HELP);
    return name === undefined ? 1 : 0;
  }
  const command = COMMANDS[name];
  if (!command) {
    throw new UsageError(`Unknown command '${name}'.`);
  }
  if (NEEDS_ENV.has(name)) {
    loadEnvFiles();
  }
  return command(rest);
}

// Exit explicitly: the SDK can leave handles open after a run. Writes are
// ordered, so once this empty write drains, everything before it has too
// (stdout to a pipe is asynchronous on macOS).
function exitAfterFlush(exitCode: number): void {
  process.stdout.write("", () => process.exit(exitCode));
}

main(process.argv.slice(2)).then(exitAfterFlush, (error: unknown) => {
  if (error instanceof UsageError) {
    const command = process.argv[2];
    const helpHint = command && COMMANDS[command] ? `${PROGRAM_NAME} ${command} --help` : `${PROGRAM_NAME} --help`;
    console.error(style.red(error.message));
    console.error(`Run '${helpHint}' for usage.`);
  } else {
    console.error(style.red(error instanceof Error ? error.message : String(error)));
  }
  exitAfterFlush(1);
});
