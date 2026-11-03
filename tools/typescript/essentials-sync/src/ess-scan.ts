#!/usr/bin/env node
// `essentials-sync scan` on its own, for the ess-scan pre-commit hook. It
// imports none of the sync command's modules, so the hook installs only the
// scanners' dependencies (see the root package.json), not @cursor/sdk.
import { runScanCommand } from "./scan-command.js";

runScanCommand(process.argv.slice(2)).then(
  (exitCode) => process.exit(exitCode),
  (error: unknown) => {
    console.error(`ess-scan: ${error instanceof Error ? error.message : String(error)}`);
    process.exit(1);
  },
);
