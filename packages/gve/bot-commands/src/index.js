// Base command
const Command = require("./command");

// Common commands
const Gifs = require("./gifs");
const Help = require("./help");

const { getStandardMessageTypes } = Command;

module.exports = {
  getStandardMessageTypes,
  Command,
  Gifs,
  Help,
};
