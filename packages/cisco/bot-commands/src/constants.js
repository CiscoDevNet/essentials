/**
 * @file Constants
 * @author Matt Norris <matnorri@cisco.com>
 */

/**
 * Name of the event fired when a user engages with
 * an attachment, e.g., an Adaptive Card.
 * @const {string}
 */
const ATTACHMENT_EVENT = "attachmentActions";

/**
 * Event name to emit when an intent is detected.
 * @const {string}
 */
const INTENT_DETECTED_EVENT = "intent detected";

/**
 * Message sent to a bot in a group space.
 * @constant {String}
 */
const MESSAGE = "message";

/**
 * Message sent to a bot in a one-on-one space.
 * @constant {String}
 */
const DIRECT_MESSAGE = "direct_message";

/**
 * Most common bot message types, e.g., "message", "direct_message".
 * Most bots will want to listen for both group and direct messages.
 * @constant {Object}
 */
const STANDARD_MESSAGE_TYPES = {
  MESSAGE,
  DIRECT_MESSAGE,
};

/**
 * Ways that a message intent can be detected -
 * with an official intent property, or through pattern-matching.
 * @constant {Object}
 */
const INTENT_MATCHING_TYPES = {
  INTENT: "intent",
  PATTERN: "pattern",
};

module.exports = {
  ATTACHMENT_EVENT,
  INTENT_DETECTED_EVENT,
  INTENT_MATCHING_TYPES,
  STANDARD_MESSAGE_TYPES,
};
