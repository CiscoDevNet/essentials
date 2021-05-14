/**
 * @file Create and configure Botkit controllers with sensible defaults.
 * @author Matt Norris <matnorri@cisco.com>
 */
const debug = require("debug")("bot-factory");

const { Botkit } = require("botkit");
const gveMiddleware = require("@gve/bot-middleware");

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
    const isConfigured = BotFactory.configureAdaptiveCards(controller);
    debug("adaptive cards:", isConfigured ? "enabled" : "disabled");
    controller._isAdaptiveCardsConfigured = isConfigured;
    return controller;
  }

  static configureAdaptiveCards(controller) {
    const webhookUrl = controller.getConfig(CONFIG_WEBHOOK_URI);
    try {
      controller.adapter.registerAdaptiveCardWebhookSubscription(webhookUrl);
      return true;
    } catch (_) {
      return false;
    }
  }

  /**
   * A command
   * @typedef {Object} Command
   * @property {String} friendlyName
   */

  static configureCommand(controller, command) {
    const friendlyName = BotFactory.getFriendlyCommandName(command);

    const results = {
      name: friendlyName,
      isConfigured: false,
    };

    try {
      // Treat command as a proper @gve/bot-commands.Command.
      command.controller = controller;
      results.isConfigured = true;
    } catch (err) {
      console.error(err);
    }

    if (!results.isConfigured) {
      // Treat command as a path to a module.
      try {
        controller.loadModule(command);
        results.isConfigured = true;
      } catch (err) {
        console.error(err);
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
    return `command: ${commandName}: ${status}`;
  }

  /**
   * Configures the intent middleware on the given controller.
   * @param {Botkit.Controller} controller - the bot controller
   * @returns {Botkit.Controller} the modified bot controller
   * @note Mutates the controller
   */
  static async configureIntentMiddleware(controller, apiId, knowledgeBaseId) {
    const results = {
      controller,
      isConnected: false,
      isKnowledgeBaseConnected: false,
    };

    if (apiId) {
      const intents = new gveMiddleware.Intents(apiId, knowledgeBaseId);
      controller.middleware.ingest.use(intents.get);
      results.isConnected = await intents.ping();
      if (knowledgeBaseId && results.isConnected) {
        results.isKnowledgeBaseConnected = true;
        debug("intent knowledge base ID:", knowledgeBaseId);
      }
    }

    return results;
  }
}

module.exports = BotFactory;
