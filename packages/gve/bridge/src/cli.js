#!/usr/bin/env node

const debug = require("debug")("bridge:cli");
const path = require("path");
const { program } = require("commander");

const Bridge = require("./index");

const VERSION = "0.1.0";

main().catch((err) => console.error(err.message));

/**
 * Runs the program, parsing any command line options first.
 */
async function main() {
  // Build the program.
  program
    .version(VERSION)
    .arguments("<source> [project]")
    .description("bridge", {
      source: "source packages directory",
      project: "destination project directory",
    })
    .option("-n, --dry-run", "perform a trial run with no changes made")
    .action(runBridge);

  // Run the program.
  await program.parseAsync();
}

/**
 * Creates a new Bridge from the source, copying the source files to the given project
 * and excluding them from repo commits and package publishing.
 * @param {String} source - the source directory
 * @param {String} project - the destination project directory
 * @param {Object} options - the program options from the command line
 * @param {Object} command - the program command
 *
 * @see https://github.com/tj/commander.js#action-handler
 */
async function runBridge(source, project = ".", options, command) {
  debug("command name:", command.name());

  let bridge;
  try {
    bridge = new Bridge(source, project, options);
  } catch (error) {
    console.error(error);
    process.exit(1);
  }

  const relativeSourcePath = path.relative(process.cwd(), bridge.source);
  const relativeDestPath =
    path.relative(process.cwd(), bridge.destination) || ".";

  console.log(`Copying from: ${relativeSourcePath}`);
  console.log(`Copying to: ${relativeDestPath}`);

  console.log("Copying packages now...");
  const destDir = await bridge.copy();
  console.log("Done.");

  console.log(`Adding ${destDir} and backups to .gitignore...`);
  bridge.gitIgnore();
  console.log("Done.");

  console.log(
    `Adding ${destDir} to project configuration so bridged packages will not be published...`
  );
  bridge.publishIgnore();
  console.log("Done.");
}
