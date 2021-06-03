/**
 * @file Analytics event constructors with default event names and property values
 * @author Matt Norris <matnorri@cisco.com>
 */

const { snakeCase } = require("snake-case");

const { logger } = require("@gve/core");

/**
 * Default event names, e.g., "Message Sent", "Message Received"
 * @type {Object}
 */
const { EVENTS } = require("./constants");

/**
 * Default property values, e.g., "unknown", -1 for an unknown number
 */
const { PROPERTY_VALUES } = require("./constants");

/**
 * Common property names, like "status".
 */
const { PROPERTY_NAMES } = require("./constants");

/**
 * Creates a new AnalyticsEvent.
 * @class
 */
class AnalyticsEvent {
  /**
   * @constructs AnalyticsEvent
   * @param {String} name - Event name
   * @param {Object} properties - Event properties
   */
  constructor(name, properties = {}) {
    this.name = name;
    this.properties = properties;
  }

  /**
   * Adds the given property and value to the event.
   * Converts the property name to `snake_case` to adhere to
   * {@link https://segment.com/docs/getting-started/04-full-install/#property-naming-best-practices|best practices}.
   * @param {String} name - Property name
   * @param {String} value - Property value
   */
  updateProperty(name, value = PROPERTY_VALUES.UNKNOWN) {
    const formattedName = snakeCase(name);
    this.properties[formattedName] = value || PROPERTY_VALUES.UNKNOWN;
  }

  get status() {
    return this._status;
  }

  set status(value) {
    this.isSuccessful(value);
  }

  get isSuccessful() {
    return this._isSuccessful;
  }

  set isSuccessful(value) {
    this._isSuccessful = !!value;
    this._status = this._isSuccessful
      ? PROPERTY_VALUES.SUCCESS
      : PROPERTY_VALUES.FAILURE;
    this.properties[PROPERTY_NAMES.STATUS] = this._status;
  }
}

function getLength(property, errorMessage = "error getting property length") {
  try {
    return property.length;
  } catch (_) {
    logger.log(errorMessage);
    return PROPERTY_VALUES.UNKNOWN_NUMBER;
  }
}

function getCount(collection, errorMessage = "error getting collection count") {
  return getLength(collection, errorMessage);
}

AnalyticsEvent.EVENTS = EVENTS;
AnalyticsEvent.PROPERTY_VALUES = PROPERTY_VALUES;
AnalyticsEvent.getCount = getCount;
AnalyticsEvent.getLength = getLength;

module.exports = {
  AnalyticsEvent,
  EVENTS,
  PROPERTY_VALUES,
};
