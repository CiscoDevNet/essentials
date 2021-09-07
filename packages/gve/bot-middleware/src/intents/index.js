/**
 * @file Middleware to detect the intent of the user.
 * @see https://googleapis.dev/nodejs/dialogflow/latest/index.html
 * @see https://cloud.google.com/dialogflow/es/docs/quick/api#detect_intent
 */

const debug = require("debug")("middleware:intents");

const dialogflow = require("@google-cloud/dialogflow");
const path = require("path");
const uuid = require("uuid");

const { ClientConfigError, ServiceUnreachableError } = require("./errors");

const DEFAULT_INTENT = "default";
const { INTENT_CONFIDENCE: CONFIDENCE_MIN } = require("./config");
const languageCode = "en-US";

/**
 * Text limit to avoid DialogFlow error:
 * INVALID_ARGUMENT: Input text exceeds 256 characters.
 */
const TEXT_LIMIT = 256;

/**
 * A Google Auth CredentialBody
 * @typedef {Object} CredentialBody
 * @property {String} client_email
 * @property {String} private_key
 * @property {String} project_id
 * @see https://github.com/googleapis/google-cloud-node/blob/master/docs/authentication.md#the-config-object
 * @see https://github.com/googleapis/google-auth-library-nodejs/blob/9ae2d30c15c9bce3cae70ccbe6e227c096005695/src/auth/credentials.ts#L81
 */

/**
 * Intent configuration
 * @typedef {Object} IntentConfig
 * @property {String} projectId - the project ID
 * @property {String} knowledgeBaseId - the knowledge base ID
 * @property {CredentialBody} credentials - credentials needed to sign into the intent API
 */

class Intents {
  constructor(config) {
    const { projectId, knowledgeBaseId, credentials } = config;
    this.projectId = projectId;
    this.knowledgeBaseId = knowledgeBaseId;
    this.credentials = credentials;
    this.get = this.get.bind(this);

    debug(`agent from project: ${projectId}`);
    debug(`knowledge base: ${knowledgeBaseId || "none"}`);
  }

  async get(bot, message, next) {
    const { text: rawText, reference, actorId: senderId } = message;
    const { id: botId } = reference.bot;

    if (rawText) {
      const isBot = senderId === botId;
      if (!isBot) {
        let text = rawText;
        if (rawText.length > TEXT_LIMIT) {
          text = rawText.slice(0, TEXT_LIMIT);
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
   * Initializes the client.
   * @returns {Promise} A promise that resolves to the initialized client
   * @throws {ServiceUnreachableError}
   * @see https://github.com/googleapis/nodejs-dialogflow/blob/fa420372a4dc6ec99e68df277050ed36b8c3091d/src/v2/sessions_client.ts#L318
   */
  async initialize() {
    try {
      await this.client.initialize();
    } catch (error) {
      throw new ServiceUnreachableError(
        `Intent detection not configured. ${error.message}`
      );
    }

    return this.client;
  }

  /**
   * Get a new sessions client.
   * @returns {dialogflow.SessionsClient} sessions client
   * @see https://stackoverflow.com/a/58511898/154065
   * @see https://cloud.google.com/dialogflow/es/docs/knowledge-connectors#detect_intent_with_knowledge_base
   */
  get client() {
    if (!this._client) {
      const { client_email, private_key, project_id } = this.credentials;
      const isValidCredentials = !!(client_email && private_key && project_id);

      if (!isValidCredentials) {
        throw new ClientConfigError(
          "Client could not be configured. The following credentials are required: client_email, private_key, project_id"
        );
      }

      const config = { credentials: this.credentials };
      this._client = this.knowledgeBaseId
        ? new dialogflow.v2beta1.SessionsClient(config)
        : new dialogflow.SessionsClient(config);
    }

    return this._client;
  }

  async ping() {
    let isReachable = false;
    const mockMessage = { id: uuid.v4() };
    try {
      // If the message can make a roundtrip to the intent detection service
      // with no errors, we know we can reach the service.
      const updatedMessage = await this.getIntent("ping", mockMessage);
      isReachable = updatedMessage.id === mockMessage.id;
    } catch (error) {
      throw new ServiceUnreachableError(
        `Intent detection failed. ${error.message}`
      );
    }

    return isReachable;
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

    const sessionPath = this.client.projectAgentSessionPath(
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

    const responses = await this.client.detectIntent(request);
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
        name = DEFAULT_INTENT;
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
