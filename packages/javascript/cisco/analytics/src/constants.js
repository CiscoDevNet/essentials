/**
 * Placeholder for unknown property value.
 * @type {String}
 */
const UNKNOWN = "unknown";

/**
 * Placeholder for unknown number property value.
 * @type {number}
 */
const UNKNOWN_NUMBER = -1;

/**
 * Event name when a message is sent by the user.
 * @type {String}
 */
const MESSAGE_SENT = "Message Sent";

/**
 * Event name when a bot sends a message to the user
 * and the user (presumably) receives it.
 * @type {String}
 */
const MESSAGE_RECEIVED = "Message Received";

const EVENTS = {
  MESSAGE_RECEIVED,
  MESSAGE_SENT,
};

const PROPERTY_NAMES = {
  STATUS: "status",
};

const PROPERTY_VALUES = {
  UNKNOWN,
  UNKNOWN_NUMBER,
  SUCCESS: "success",
  FAILURE: "failure",
};

module.exports = {
  EVENTS,
  PROPERTY_NAMES,
  PROPERTY_VALUES,
};
