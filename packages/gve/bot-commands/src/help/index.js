const debug = require("debug")("commands:help");

const Command = require("../command");

const event = { name: "Help Viewed" };
const preamble = `Hello! 👋 I'm here to help.\n
Try one of these commands:`;
const defaultPhrases = [
  "/help",
  "help",
  "hello",
  "hi",
  "hey",
  "I need help",
  "please help",
  "help please",
  "are you there",
  "anyone there",
  "is anyone there",
  "test",
];

class Help extends Command {
  constructor(config = { intent: "help", phrases: defaultPhrases }) {
    super(config);
    this.handleText = this.getHelp.bind(this);
    this.buildHelp = this.buildHelp.bind(this);
    this.commands = {};
  }

  addCommand(commandName, explanation, showCommand = () => true) {
    this.commands[commandName] = {
      explanation: explanation || commandName,
      showCommand,
    };
    debug(`command added: ${commandName}`);
  }

  async getHelp(bot, message) {
    debug("help requested");

    const text = `${preamble}\n
${this.buildHelp(message, '"', "")}`;
    const markdown = `${preamble}\n
${this.buildHelp(message)}`;

    const response = { text, markdown, event };
    await bot.reply(message, response);
  }

  /**
   * Builds a formatted help string. Defaults to Markdown.
   *
   * @param {Object} commands commands to print
   * @param {*} format format of the printed command
   * @param {*} bullet character for the bulleted list
   * @returns {String} formatted help
   */
  buildHelp(message, format = "**", bullet = "-") {
    this.addCommand("help", "I'll show you this message 😉");
    const help = [];
    for (const [commandName, command] of Object.entries(this.commands)) {
      const { explanation, showCommand } = command;
      if (showCommand(message._person)) {
        // If the bullet is empty, don't pad with a space.
        const prefix = bullet === "" ? "" : `${bullet} `;
        // Surround the command with its formatting.
        const formatted = `${prefix}${format}${commandName}${format}`;
        help.push(`${formatted} - ${explanation}`);
      }
    }

    return help.join("\n");
  }
}

module.exports = Help;
