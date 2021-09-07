/**
 * @file Create and configure Botkit controllers with sensible defaults.
 * @author Matt Norris <matnorri@cisco.com>
 */
const debug = require("debug")("bot-factory");

const { Botkit } = require("botkit");
const gveMiddleware = require("@gve/bot-middleware");

const { MiddlewareConfigError } = require("./errors");

const {
  ENABLED,
  DISABLED,
  CONFIG_WEBHOOK_URI,
  MESSAGES_API_PATH,
} = require("./constants");

const CONFIG = {
  webhookUrl: MESSAGES_API_PATH,
};

class BotFactory {
  static create(adapter, config = CONFIG) {
    const { webhookUrl = MESSAGES_API_PATH } = config;
    const controller = new Botkit({ adapter, webhook_uri: webhookUrl });
    debug("controller: created");
    BotFactory.configureAdaptiveCards(controller);
    return controller;
  }

  static configureAdaptiveCards(controller) {
    let isConfigured;
    const webhookUrl = controller.getConfig(CONFIG_WEBHOOK_URI);
    try {
      controller.adapter.registerAdaptiveCardWebhookSubscription(webhookUrl);
      isConfigured = true;
    } catch (_) {
      isConfigured = false;
    }

    controller._isAdaptiveCardsConfigured = isConfigured;
    return isConfigured;
  }

  /**
   * A command
   * @typedef {Object} Command
   * @property {String} friendlyName
   */

  static configureCommand(controller, command, commandName) {
    const friendlyName =
      commandName || BotFactory.getFriendlyCommandName(command);

    const results = {
      name: friendlyName,
      isConfigured: false,
    };

    try {
      // Treat command as a proper @gve/bot-commands.Command.
      command.controller = controller;
      results.isConfigured = true;
    } catch (error) {
      results.error = error;
    }

    if (!results.isConfigured) {
      // Treat command as a path to a module.
      try {
        controller.loadModule(command);
        results.isConfigured = true;
      } catch (error) {
        results.error = error;
      }
    }

    return results;
  }

  static getFriendlyCommandName(command) {
    let friendlyName;

    ({ friendlyName } = command);
    if (!friendlyName) {
      friendlyName = command.name || command.intent;
    }

    if (!friendlyName && command.constructor) {
      friendlyName = command.constructor.name;
    }

    return friendlyName;
  }

  static getCommandLog(commandName, isEnabled) {
    const status = isEnabled ? ENABLED : DISABLED;
    const formattedName = commandName[0].toUpperCase() + commandName.substr(1);
    return `${formattedName} command ${status}.`;
  }

  /**
   * Intent configuration
   * @typedef {Object} IntentConfig
   * @property {String} projectId - the project ID
   * @property {String} knowledgeBaseId - the knowledge base ID
   * @property {CredentialBody} credentials - credentials needed to sign into the intent API
   */

  /**
   * Configures the intent middleware on the given controller.
   * @param {Botkit.Controller} controller - the bot controller
   * @returns {Botkit.Controller} the modified bot controller
   * @note Mutates the controller
   */
  static async configureIntentMiddleware(controller, intentConfig) {
    const intents = new gveMiddleware.Intents(intentConfig);

    try {
      await intents.initialize();
      controller.middleware.ingest.use(intents.get);

      // Get knowledge base details.
      let knowledgeBase;
      const { knowledgeBaseId } = intentConfig;
      if (knowledgeBaseId) {
        knowledgeBase = {
          id: knowledgeBaseId,
          isConnected: true,
        };
      }

      // Attach middleware details to the controller.
      controller.middleware.$intents = {
        isConnected: true,
        knowledgeBase,
      };
    } catch (error) {
      throw new MiddlewareConfigError(error.message);
    }

    return controller;
  }
}

module.exports = BotFactory;
