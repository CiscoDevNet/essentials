#!/usr/bin/env node
// `scan` on its own, for the ess-scan pre-commit hook. It imports none of the
// sync command's modules, so the hook never loads @cursor/sdk and needs no
// install: Node strips the types and secretlint comes from npx.
import { runScanCommand } from "./scan-command.ts";

runScanCommand(process.argv.slice(2)).then(
  (exitCode) => {
    process.exitCode = exitCode;
  },
  (error: unknown) => {
    console.error(`ess-scan: ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  },
);
