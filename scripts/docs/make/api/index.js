#!/usr/bin/env node

const colors = require("colors/safe");
const fs = require("fs").promises;
const jsdoc2md = require("jsdoc-to-markdown");
const parseArgs = require("minimist");

// Define constants.

const ARG_DEFAULTS = {
  destination: "docs/docs/api.md",
};
const FILES = "packages/gve/!(node_modules)/src/**/*.js";
const FRONT_MATTER = "---\nid: api\ntitle: API\nsidebar_position: 4\n---";

// Get the script arguments.

const args = process.argv.slice(2);
const argv = parseArgs(args, { default: ARG_DEFAULTS });
const { destination } = argv;

// Write the markdown file.

console.log(`Writing API docs to ${colors.bold(destination)}...`);

const options = { files: FILES, "example-lang": "js" };
jsdoc2md
  .render(options)
  .then(writeMarkdownFile)
  .then(() => console.log(colors.green("Done.\n")))
  .catch((error) => console.error(`${colors.red("Error: ")}${error.message}`));

/**
 * Write the generated API and its frontmatter to the markdown file.
 * @param {string} text text to write to the file
 * @returns {Promise<string>} the complete file text
 */
async function writeMarkdownFile(text) {
  const fileText = `${FRONT_MATTER}\n${text}`;
  return await fs.writeFile(destination, fileText);
}
