/**
 * @file Middleware to detect the intent of the user.
 * @see https://googleapis.dev/nodejs/dialogflow/latest/index.html
 * @see https://cloud.google.com/dialogflow/es/docs/quick/api#detect_intent
 */

const debug = require("debug")("middleware:intents");

const dialogflow = require("@google-cloud/dialogflow");
const path = require("path");
const uuid = require("uuid");

const defaultIntent = "default";
const { CREDENTIALS, INTENT_CONFIDENCE: CONFIDENCE_MIN } = require("./config");
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
    const config = { credentials: CREDENTIALS };
    // If a Knowledge Base ID is configured, use Beta.
    if (this.knowledgeBaseId) {
      return new dialogflow.v2beta1.SessionsClient(config);
    }

    return new dialogflow.SessionsClient(config);
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

  async ping() {
    let isServiceReachable = false;
    const mockMessage = { id: uuid.v4() };
    try {
      // If the message can make a roundtrip to the intent detection service
      // with no errors, we know we can reach the service.
      const updatedMessage = await this.getIntent("ping", mockMessage);
      isServiceReachable = updatedMessage.id === mockMessage.id;
    } catch (error) {
      console.error(`intent detection ping failed: ${error.message}`);
    }

    return isServiceReachable;
  }

  /**
   * Get the intent.
   * @param {String} text user text
   * @param {Object} message system message
   * @returns {Object} system message with attached intent
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

    const { intent } = result;
    let {
      fulfillmentText,
      knowledgeAnswers,
      intentDetectionConfidence: confidence = 0,
    } = result;

    // Handle nulls.
    const sentiment = result.sentimentAnalysisResult || undefined;

    let answers;
    if (knowledgeAnswers) {
      ({ answers } = knowledgeAnswers);
    }

    if (intent && !intent.isFallback) {
      let { displayName: name } = intent;
      const { parameters } = intent;

      debug(
        `"${text}": intent matched: "${name}" with ${confidence} confidence`
      );

      // Fall back to default intent if confidence isn't met.
      const isConfidenceMet = confidence >= CONFIDENCE_MIN;
      if (!isConfidenceMet) {
        name = defaultIntent;
        confidence = 1;
        debug(`changed intent to "${name}"`);
      }

      message._intent = {
        name,
        confidence,
        fulfillmentText,
        sentiment,
        parameters,
        answers,
      };
    } else {
      debug(`"${text}": intent matched: none`);
    }

    return message;
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
