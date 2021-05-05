/**
 * @file Middleware to detect the intent of the user.
 * @see https://googleapis.dev/nodejs/dialogflow/latest/index.html
 * @see https://cloud.google.com/dialogflow/es/docs/quick/api#detect_intent
 */

const debug = require("debug")("middleware:intents");

const dialogflow = require("@google-cloud/dialogflow");
const path = require("path");

const defaultIntent = "default";
const { INTENT_CONFIDENCE: confidenceThreshold } = require("./config");
const languageCode = "en-US";

/**
 * Text limit to avoid DialogFlow error:
 * INVALID_ARGUMENT: Input text exceeds 256 characters.
 */
const textLimit = 256;

class Intents {
  constructor(projectId, knowledgeBaseId) {
    this.projectId = projectId;
    this.knowledgeBaseId = knowledgeBaseId;
    this.sessionClient = this._getSessionsClient();
    this.get = this.get.bind(this);

    debug(`agent from project: ${projectId}`);
    debug(`knowledge base: ${knowledgeBaseId || "none"}`);
  }

  /**
   * Get a new sessions client.
   * @returns {dialogflow.SessionsClient} sessions client
   * @see https://stackoverflow.com/a/58511898/154065
   * @see https://cloud.google.com/dialogflow/es/docs/knowledge-connectors#detect_intent_with_knowledge_base
   */
  _getSessionsClient() {
    // If a Knowledge Base ID is configured, use Beta.
    if (this.knowledgeBaseId) {
      return new dialogflow.v2beta1.SessionsClient();
    }

    return new dialogflow.SessionsClient();
  }

  async get(bot, message, next) {
    const { text: rawText, reference, actorId: senderId } = message;
    const { id: botId } = reference.bot;

    if (rawText) {
      if (senderId !== botId) {
        let text = rawText;
        if (rawText.length > textLimit) {
          text = rawText.slice(0, textLimit);
        }

        await this.getIntent(text, message);
      } else {
        debug("skipping, sender is a bot");
      }
    } else {
      debug("skipping, sending attachment");
    }

    next();
  }

  /**
   * Get the intent.
   * @param {String} text user text
   * @param {Object} message system message
   * @see https://googleapis.dev/nodejs/dialogflow/latest/index.html
   */
  async getIntent(text, message) {
    const { id: sessionId, _intentContexts: contexts } = message;
    const sessionPath = this.sessionClient.projectAgentSessionPath(
      this.projectId,
      sessionId
    );

    const queryParams = {};
    Object.assign(queryParams, this._getKnowledgeBase());

    const hasContexts = contexts && contexts.length > 0;
    if (hasContexts) {
      Object.assign(queryParams, { contexts });
    }

    const request = {
      session: sessionPath,
      queryInput: {
        text: {
          text,
          languageCode,
        },
      },
      queryParams,
    };

    const responses = await this.sessionClient.detectIntent(request);
    const result = responses[0].queryResult;

    const { intent, sentimentAnalysisResult: sentiment = undefined } = result;
    let { intentDetectionConfidence: confidence = 0 } = result;

    if (intent) {
      let { displayName: name } = intent;
      const { parameters } = intent;

      debug(`"${text}" matched intent "${name}" with ${confidence} confidence`);

      // Fall back to default intent.
      if (confidence < confidenceThreshold) {
        name = defaultIntent;
        confidence = 1;
        debug(`changed intent to "${name}"`);
      }

      message._intent = { name, confidence, sentiment, parameters };
    } else {
      debug(`no match for ${text}`);
    }
  }

  /**
   * Returns the knowledge base configuration to send to endpoint.
   * @returns {Object} knowledge base config
   * @see https://stackoverflow.com/a/58511898/154065
   * @see https://cloud.google.com/dialogflow/es/docs/knowledge-connectors#detect_intent_with_knowledge_base
   */
  _getKnowledgeBase() {
    let knowledgeBase;

    if (this.knowledgeBaseId) {
      const KNOWLEDGE_BASE_PATH = path.join(
        "projects",
        this.projectId,
        "knowledgeBases",
        this.knowledgeBaseId
      );

      knowledgeBase = { knowledgeBaseNames: [KNOWLEDGE_BASE_PATH] };
    }

    return knowledgeBase;
  }
}

module.exports = Intents;
