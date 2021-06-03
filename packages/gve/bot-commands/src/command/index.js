/**
 * @file Base command to determine intent from a user message.
 * @author Matt Norris <matnorri@cisco.com>
 */

const debug = require("debug")("commands");

const { ControllerAssignError } = require("./errors");

/**
 * Confidence threshold - if the confidence falls below
 * this number, the intent is not clear and does not trigger.
 * @const {number}
 */
const { INTENT_CONFIDENCE } = require("./config");

const {
  ATTACHMENT_EVENT,
  INTENT_DETECTED_EVENT,
  INTENT_MATCHING_TYPES,
  STANDARD_MESSAGE_TYPES,
} = require("./constants");

const REGEX_IGNORE_CASE = "i";

/**
 * A regular expression that never matches anything.
 * @constant {RegExp}
 * @see https://2ality.com/2012/09/empty-regexp.html
 */
const REGEX_NEVER_MATCH = /.^/;

/**
 * Command configuration
 * @typedef {Object} CommandConfig
 * @property {String} intent - name of the intent
 * @property {string[]} messageTypes - Types of messages to listen for, e.g., a direct (1-on-1) message
 * @property {string[]} phrases - Phrases to listen for
 * @property {function} handleText - Handles message text
 * @property {function} handleAttachment - Handles message attachment actions, e.g., Adaptive Card clicks
 * @property {string} friendlyName - Friendly name of the command
 */

/**
 * Creates a new base Command that handles a particular intent.
 * Specific commands
 * @class
 */
class Command {
  /**
   * Creates a new command.
   * Listens to direct and group messages by default.
   * @param {CommandConfig} config - optional configuration
   */
  constructor(
    config = {
      messageTypes: Object.values(STANDARD_MESSAGE_TYPES),
    }
  ) {
    const {
      intent,
      messageTypes = Object.values(STANDARD_MESSAGE_TYPES),
      handleText = this.defaultHandleText.bind(this),
      handleAttachment = this.defaultHandleAttachment.bind(this),
    } = config;

    this.intent = intent;
    const { phrases, friendlyName } = this._getDefaultConfig(config);

    this.messageTypes = messageTypes;
    this.phrases = phrases;
    this.friendlyName = friendlyName;
    this.getIntent = this.getIntent.bind(this);
    this.handleText = handleText;
    this.handleAttachment = handleAttachment;
  }

  _getDefaultConfig(config) {
    let { phrases, friendlyName } = config;

    if (!phrases && this.intent) {
      phrases = Command._getDefaultPhrases(this.intent);
    }

    if (!friendlyName && this.intent) {
      friendlyName = this.intent;
    }

    return { phrases, friendlyName };
  }

  static _getDefaultPhrases(phrase) {
    return phrase ? [phrase] : [];
  }

  /**
   * See "Getters and Setters":
   * @see https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Objects/Inheritance
   */

  get controller() {
    return this._controller;
  }

  set controller(newController) {
    try {
      this.updateController(newController);
    } catch (err) {
      throw new ControllerAssignError(err.message);
    }
  }

  get phrases() {
    return this._phrases;
  }

  set phrases(newPhrases) {
    this._phrases = newPhrases;
    this.phraseExpression = this._phrases
      ? Command.getPhraseExpression(this._phrases)
      : new RegExp(REGEX_NEVER_MATCH);
    debug(`phrase: ${this.phraseExpression}`);
  }

  /**
   * Configures the controller to listen for the command phrases
   * and attachment actions, e.g., Adaptive Card actions.
   * @param {Botkit} controller
   */
  updateController(controller) {
    this._controller = controller;
    this._controller.hears(this.getIntent, this.messageTypes, this.handleText);
    this._controller.on(ATTACHMENT_EVENT, this.handleAttachment);

    return this._controller;
  }

  /**
   * Joins the given phrases into a regular expression.
   * @param {Array} phrases - The phrases to join
   * @returns {RegExp} joined phrases
   */
  static getPhraseExpression(phrases) {
    return RegExp(
      `^${phrases.reduce(Command._joinPhrases)}`,
      REGEX_IGNORE_CASE
    );
  }

  /**
   * Joins the phrases joined so far with the next phrase.
   * @param {String} joined - Phrases joined so far
   * @param {String} phrase - Next phrase to join
   * @returns {String} joined phrases
   * @private
   */
  static _joinPhrases(joined, phrase) {
    return `${joined}|^${phrase}`;
  }

  /**
   * Handles text commands by default.
   * Prints a debug statement.
   */
  defaultHandleText() {
    debug(`${this.constructor.name} handle command`);
  }

  /**
   * Handles attachments by default.
   * Prints a debug statement.
   */
  defaultHandleAttachment() {
    debug(`${this.constructor.name} handle attachment`);
  }

  /**
   * A message
   * @typedef {Object} Message
   * @property {Object} _intent - The detected user intent
   * @property {string} text - The message text
   */

  /**
   * Returns the detected intent of the message.
   * If there is no "official" intent attached, uses pattern-matching
   * to determine the intent from the command's list of phrases.
   * @see https://botkit.ai/docs/v4/reference/core.html#hears
   * @fires Intent#detected
   * @param {Message} message
   * @returns {boolean} true if intent was detected, false if not
   */
  getIntent(message) {
    const { _intent: intent } = message;
    let shouldEmitEvent = false;
    let matchType = INTENT_MATCHING_TYPES.INTENT;
    let name;
    let confidence;
    if (intent) {
      // Get the intent, if one is detected.
      ({ name, confidence = 0 } = intent);
      const isIntentMatched = this.matchIntent(intent);
      const isConfidenceReached = confidence >= INTENT_CONFIDENCE;
      shouldEmitEvent = isIntentMatched && isConfidenceReached;
    } else {
      // Otherwise, fall back to phrases.
      shouldEmitEvent = this._matchPhrase(message);
      matchType = INTENT_MATCHING_TYPES.PATTERN;
    }

    if (shouldEmitEvent) {
      const payload = {
        commandName: this.constructor.name,
        intent: name,
        confidence,
        type: matchType,
      };
      debug(INTENT_DETECTED_EVENT, payload);
    }

    return shouldEmitEvent;
  }

  matchIntent(intent) {
    if (this.intent) {
      return this._matchNamedIntent(intent);
    }

    return Command._matchKnowledgeIntent(intent);
  }

  /**
   * Returns true if the intent name matches this intent, false otherwise.
   * @param {String|Object} intent
   * @see https://stackoverflow.com/a/9436948/154065
   * @returns {Boolean} true if the intent name matches this intent
   */
  _matchNamedIntent(intent) {
    const isString = typeof intent === "string" || intent instanceof String;
    if (isString) {
      return intent === this.intent;
    }

    try {
      return intent.name === this.intent;
    } catch (_) {
      return false;
    }
  }

  static _matchKnowledgeIntent(intent) {
    const { answers, fulfillmentText, name } = intent;
    const hasAnswers = !!answers;
    const hasTextResponse = !!fulfillmentText;

    try {
      const isFromKnowledgeBase = name.startsWith("Knowledge.KnowledgeBase.");
      return isFromKnowledgeBase && hasAnswers && hasTextResponse;
    } catch (_) {
      return false;
    }
  }

  /**
   * A message
   * @typedef {{text: String}} Message
   */

  /**
   * Returns true if the user's message text matches the list of command phrases.
   * @param {Message} message - the user's message
   * @returns {boolean} true if the user's message matches a known command
   * @private
   */
  _matchPhrase(message) {
    return Command.matchPhrase(message, this.phraseExpression);
  }

  /**
   * Returns true if the user's message text matches the list of command phrases.
   * @param {Message|string} message - the user's message or message text
   * @param {RegExp} phrase - the phrase to match
   * @returns {boolean} true if the user's message matches a known command
   */
  static matchPhrase(message, phrase) {
    const { text: messageText = message } = message;
    return !!messageText.match(phrase);
  }
}

module.exports = Command;
