/**
 * @file Middleware to track user events.
 * @author Matt Norris <matnorri@cisco.com>
 */

const debug = require("debug")("middleware:analytics");

const axios = require("axios");
const emailAddresses = require("email-addresses");
const uuidv1 = require("uuid/v1");

const { EVENTS, PROPERTY_VALUES } = require("@gve/analytics");

const { ANALYTICS_URL } = require("./config");

const TRACKING_MESSAGE_REASON = "Message is a standard message.";
const TRACKING_DIALOG_REASON = "Message is a part of a dialog.";
const TRACKING_CARD_REASON = "Message is a card.";

/**
 * User data.
 *
 * Responses sent from the bot are not sent to a particular user,
 * but to a Webex Teams space. In order to track events
 * from the {@link User}'s perspective, we need to internally track user data.
 * @typedef {Object} User
 * @property {String} user_id - Encrypted user ID
 * @property {String} domain - Domain of the user, e.g., cisco.com
 */

/**
 * Partial known space data.
 * @typedef {Object} space
 * @property {String} space_id - space ID
 * @property {String} space_type - space type, e.g., "direct" or "group"
 */

/**
 * Known spaces.
 * Keys are of type {@link Space.space_id}.
 * Properties are of type {@link Space}.
 * @typedef {Map} Spaces
 */
let spaces = new Map();

/**
 * Map of user property names and formatting functions.
 *
 * @typedef {Object} UserProp
 * @property {String} name - user property name
 * @property {function} format - function to format the user property name
 */

/**
 * Middleware to track user events.
 *
 * Properties sent to the analytics service are in snake_case,
 * based on {@link https://segment.com/academy/collecting-data/naming-conventions-for-clean-data/|Segment naming conventions}.
 *
 * Some properties are encrypted or excluded,
 * based on {@link https://wiki.cisco.com/display/CTGPrivacy/Privacy+Rules+for+Spark+Message+Logs+and+Analytics | Webex Teams recommendations}.
 *
 * - Users identified by Webex Teams' hashed ID
 * - Org names/domain names are reported (not org ID)
 * - Single event records do not include both sides of a communication
 */
class Analytics {
  /**
   * @constructs Analtyics
   * @param {String} apiKey the analytics service API key
   * @param {Object} config configuration details
   * @param {Object} config.appEnvironment application environment, e.g., development, staging
   * @param {Object} config.appVersion] application version
   * @param {String} config.url the analytics service URL
   * @param {Array<String|UserProps>} config.userProps - the additional user properties to track
   */
  constructor(apiKey, config = {}) {
    this.apiKey = apiKey;

    const {
      environment = PROPERTY_VALUES.UNKNOWN,
      url = ANALYTICS_URL,
      userProps = [],
      version = PROPERTY_VALUES.UNKOWN,
    } = config;

    this.appEnvironment = environment;
    this.appVersion = version;
    this.url = url;
    this.userProps = userProps;

    this.trackUserMessage = this.trackUserMessage.bind(this);
    this.trackBotMessage = this.trackBotMessage.bind(this);

    debug(`initialized`);
    debug(`sending events to: ${this.url}`);
  }

  /**
   * Sets additional user properties to pick from each incoming message.
   * @param {Map|Array<Array<String>>} props - user property names and friendly names
   */
  set userProps(props) {
    this._userProps = new Map(props);
  }

  get userProps() {
    return this._userProps;
  }

  /**
   * Tracks messages from the user to the bot.
   * @note Use with the middleware `receive` function.
   *
   * @param {*} bot
   * @param {*} message
   * @param {*} next
   *
   * @example
   *
   *  const analyticsMiddleware = new Analytics();
   *  controller.middleware.receive.use(analyticsMiddleware.trackUserMessage);
   *
   */
  trackUserMessage(bot, message, next) {
    try {
      const {
        incoming_message: incomingMessage,
        reference,
        _person: user,
      } = message;

      const { bot: botRecipient, channelId: platform } = reference;
      const { from: sender } = incomingMessage;

      if (botRecipient.id !== sender.id) {
        debug(`user sending message to bot`);

        const {
          id: message_id,
          roomId: space_id,
          roomType: space_type,
          text,
          created: timestamp,
        } = message;

        // Message length may be zero if the user is interacting with a card.
        const message_length = text ? text.length : 0;

        const event_properties = {
          message_id,
          message_length,
          space_id,
          space_type,
        };

        const basicInfo = this._getStandardInfo(timestamp);

        const userInfo = this._getUserInfo(sender);
        const additionalUserProps = this._getAdditionalUserProps(user);
        Object.assign(userInfo.user_properties, additionalUserProps);

        const analyticsEvent = {
          event_type: EVENTS.MESSAGE_SENT,
          event_properties,
          platform,
          ...basicInfo,
          ...userInfo,
        };

        // Store partial space data for the bot's response.
        // Its message back has far less information, so we need this to be complete.
        spaces.set(space_id, { space_id, space_type });

        debug(`tracking user message to bot`);
        this._track(analyticsEvent);
      }
    } catch (err) {
      // Catch and log all errors rather than break the bot.
      console.error(`bot receive: ${err.message}`);
    }

    next();
  }

  /**
   * Tracks messages from the bot to the user.
   * @note Use with the middleware `send` function.
   *
   * @param {*} bot
   * @param {*} message
   * @param {*} next
   *
   * @example
   *
   *  const analyticsMiddleware = new Analytics();
   *  controller.middleware.send.use(analyticsMiddleware.trackBotMessage);
   *
   */
  trackBotMessage(bot, message, next) {
    const { shouldTrack, reason } = this._shouldTrack(message);

    const formattedReason = reason ? `: ${reason}` : "";
    debug(`bot sending message to user${formattedReason}`);

    try {
      if (shouldTrack) {
        const {
          channelData: messageData,
          channelId: platform,
          conversation: minimalSpaceInfo,
          recipient,
          replyToId: message_received_id,
        } = message;

        // Default to "Message Received" and no additional properties.
        let event_type = EVENTS.MESSAGE_RECEIVED;
        let additionalProperties = {};

        // Get a specific event name and additional properties, if available.
        if (messageData) {
          const analyticsEvent =
            messageData._analyticsEvent || messageData.event;
          try {
            ({
              name: event_type,
              properties: additionalProperties,
            } = analyticsEvent);
          } catch (_) {
            debug(`no analytics event`);
          }
        }

        const spaceInfo = this._getSpaceInfo(minimalSpaceInfo);
        const { space_id, space_type } = spaceInfo;

        const event_properties = {
          space_id,
          space_type,
          message_received_id,
          ...additionalProperties,
        };

        const basicInfo = this._getStandardInfo();
        const userInfo = this._getUserInfo(recipient);

        const analyticsEvent = {
          event_type,
          event_properties,
          platform,
          ...basicInfo,
          ...userInfo,
        };

        debug(`tracking bot message to user`);
        this._track(analyticsEvent);
      }
    } catch (err) {
      // Catch and log all errors rather than break the bot.
      console.error(`ERROR: send: ${err.message}`);
    }

    next();
  }

  /**
   * Get the additional, desired user properties.
   * @param {Object} user - additional user info attached to the message
   * @returns {Object} additional user properties
   */
  _getAdditionalUserProps(user) {
    const additionalUserProps = {};
    this._userProps.forEach((friendlyName, propName) => {
      // If no friendly name is provided, use the given property name.
      const userPropKey = friendlyName || propName;

      const value = user[propName] || PROPERTY_VALUES.UNKNOWN;
      additionalUserProps[userPropKey] = value;
    });

    return additionalUserProps;
  }

  /**
   * The space with the message.
   * This space has only one property: an ID.
   *
   * @typedef {Object} MinimalSpace
   * @param {String} id - ID of the space with the message
   */

  /**
   * Gets more space information.
   * @param {MinimalSpace} minimalSpace - space with the message
   * @returns {Object} space with more details
   */
  _getSpaceInfo(minimalSpace) {
    const { id: spaceId } = minimalSpace;
    const space = {
      space_id: spaceId,
      space_type: PROPERTY_VALUES.UNKNOWN,
    };

    const cachedSpace = spaces.get(spaceId);
    Object.assign(space, cachedSpace || {});

    return space;
  }

  /**
   * If and why an event should be tracked or not tracked
   * @typedef {Object} ShouldTrack
   * @property {boolean} shouldTrack - true if an event should be tracked, false otherwise
   * @property {String} reason - reason an event is tracked or not tracked
   */

  /**
   * Returns if and why an event should be tracked.
   * @param {Botkit.Message} message
   * @returns {ShouldTrack} if an event should be tracked and the reason for it
   * @private
   */
  _shouldTrack(message) {
    let shouldTrack = true;
    let reason = TRACKING_MESSAGE_REASON;

    const { attachments, inputHint, recipient } = message;
    const isPartOfDialog = inputHint === "acceptingInput" || !recipient;
    const isCard = !recipient && attachments && attachments.length;

    if (isPartOfDialog || isCard) {
      shouldTrack = false;
      reason = isPartOfDialog ? TRACKING_DIALOG_REASON : TRACKING_CARD_REASON;
    }

    return { shouldTrack, reason };
  }

  /**
   * The user (person, bot) receiving a message.
   * This user has a minimal number of properties.
   *
   * @typedef {Object} MinimalUser
   * @param {String} id - ID of the user receiving the message
   * @param {String} name - email of the user receiving the message
   */

  /**
   * User information for an analytics event
   *
   * @typedef {Object} UserInfo
   * @property {string} user_id - user ID
   * @property {Object} user_properties - user properties
   * @property {string} user_properties.app_environment - the app environment, e.g., "development", "staging"
   * @property {string} user_properties.domain - the domain of the user, e.g., "cisco.com"
   */

  /**
   * Gets the user properties for the analytics event.
   * @param {MinimalUser} user
   * @returns {UserInfo} user information for an analytics event
   */
  _getUserInfo(user) {
    const { id: user_id, name: email } = user;
    let domain = PROPERTY_VALUES.UNKNOWN;

    try {
      ({ domain = PROPERTY_VALUES.UNKNOWN } = emailAddresses.parseOneAddress(
        email
      ));
    } catch (_) {
      debug(`domain: not found from email: ${email}`);
    }

    const user_properties = {
      app_environment: this.appEnvironment,
      domain,
    };

    return { user_id, user_properties };
  }

  /**
   * Gets information standard to all analytics events.
   * @param {number} timestamp - time in seconds
   * @returns {Object} app version and time
   */
  _getStandardInfo(timestamp) {
    const date = timestamp ? new Date(timestamp) : new Date();

    return {
      app_version: this.appVersion,
      time: getTime(date),
    };
  }

  /**
   * Tracks the event.
   * @private
   * @param {Object} event the event to track
   */
  _track(event) {
    // If no insert ID is given, create one to uniquely identify this event
    // in case the event is duplicated.
    // For example, an event can be POSTed twice during a retry.
    const { insert_id = uuidv1() } = event;
    event.insert_id = insert_id;

    const events = [event];
    const body = {
      api_key: this.apiKey,
      events,
    };

    axios
      .post(this.url, body)
      .then(function (response) {
        if (response.status !== 200) {
          console.error(`tracking failure: ${response}`);
        } else {
          debug(`tracking successful: ${event.insert_id}`);
        }
      })
      .catch(function (error) {
        console.error(error);
      });
  }
}

/**
 * Attach "static" property to the class.
 * @see https://stackoverflow.com/a/48012789/154065
 */
Analytics.PROPERTY_VALUES = PROPERTY_VALUES;

/**
 * Returns the date's time in seconds.
 * @param {Date} date the date to convert
 */
function getTime(date) {
  return Math.round(date.getTime() / 1000);
}

module.exports = Analytics;
