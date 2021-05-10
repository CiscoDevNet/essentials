/**
 * @file Create and configure Botkit controllers with sensible defaults.
 * @author Matt Norris <matnorri@cisco.com>
 */
const debug = require("debug")("bot-factory");
const path = require("path");

const { Botkit } = require("botkit");
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

  static configureCommand(controller, commandPath, friendlyCommandName) {
    if (!friendlyCommandName) {
      ({ name: friendlyCommandName } = path.parse(commandPath));
    }

    const command = {
      path: commandPath,
      name: friendlyCommandName,
      isConfigured: true,
    };
    try {
      controller.loadModule(commandPath);
    } catch (_) {
      command.isConfigured = false;
    }
    return command;
  }

  static getCommandLog(commandName, isEnabled) {
    const status = isEnabled ? ENABLED : DISABLED;
    return `command: ${commandName}: ${status}`;
  }
}

module.exports = BotFactory;
