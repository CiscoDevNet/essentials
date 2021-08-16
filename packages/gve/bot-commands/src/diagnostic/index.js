const Command = require("../command");

/**
 * Analytics event.
 */
const analyticsEvent = {
  name: "Diagnostic Viewed",
};

const DEFAULT_INTENT = "diagnose";
const DEFAULT_PHRASES = [
  "run a diagnostic",
  "run diagnostic",
  "diagnostic",
  "diagnose",
];

const DEFAULT_NAME = "Bot";
const DEFAULT_ENVIRONMENT = "an unknown";
const DEFAULT_CONFIG = {
  intent: DEFAULT_INTENT,
  phrases: DEFAULT_PHRASES,
  name: DEFAULT_NAME,
};

class Diagnostic extends Command {
  constructor(config = DEFAULT_CONFIG) {
    Object.assign(config, { intent: DEFAULT_INTENT, phrases: DEFAULT_PHRASES });
    super(config);
    const {
      name = DEFAULT_NAME,
      version,
      description,
      environment,
      url,
    } = config;
    this.name = name;
    this.version = version;
    this.description = description;
    this.environment = environment;
    this.url = url;
    this.handleText = this.getDiagnostic.bind(this);
  }

  async getDiagnostic(bot, message) {
    const response = {
      text: this.text,
      markdown: this.markdown,
      _analyticsEvent: analyticsEvent,
    };
    await bot.reply(message, response);
  }

  get markdown() {
    const environment = this.environment
      ? `the _${this.environment}_`
      : DEFAULT_ENVIRONMENT;
    const preamble = `_${this.nameAndVersion}_ is running in ${environment} environment.`;
    const urlInstruction = this.url ? `Visit ${this.url}` : undefined;
    const parts = [preamble, this.description, urlInstruction];
    return parts.filter(Boolean).join("\n\n");
  }

  get text() {
    const environment = this.environment
      ? `the ${this.environment}`
      : DEFAULT_ENVIRONMENT;
    const preamble = `${this.nameAndVersion} is running in ${environment} environment.`;
    const urlInstruction = this.url ? `Visit ${this.url}` : undefined;
    const parts = [preamble, this.description, urlInstruction];
    return parts.filter(Boolean).join("\n\n");
  }

  get nameAndVersion() {
    if (this.version) {
      return `${this.name} ${this.version}`;
    } else {
      return this.name;
    }
  }
}

module.exports = Diagnostic;
