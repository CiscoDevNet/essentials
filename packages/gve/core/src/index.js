/**
 * @file Common functions for all apps and systems
 * @author Matt Norris <matnorri@cisco.com>
 */

const debug = require("debug")("modules:core");

const forceBoolean = require("force-boolean").default;
const nodeUrl = require("url");
const normalizeUrl = require("normalize-url");

function getDefaultValue(envVariable, defaultValue) {
  let value = forceBoolean(envVariable);
  if (envVariable === undefined || envVariable === "") {
    value = defaultValue;
  }
  return value;
}

/**
 * Returns the base domain from the given URL.
 * @param {URL|String} url
 * @returns {String} domain of the URL
 */
function getDomain(url) {
  let domain;

  try {
    const normalizedUrl = _normalizeMalformedUrl(url);
    ({ hostname: domain } = nodeUrl.parse(normalizedUrl));
    debug(`domain: ${domain}: extracted from: "${url}"`);
  } catch (_) {
    debug(`domain: not extracted from: "${url}"`);
  }

  return domain;
}

/**
 * Returns a normalized URL.
 * @see https://www.npmjs.com/package/normalize-url
 * @param {String} url - URL to normalize
 * @returns {String} Normalized URL or empty string
 * @private
 */
function _normalizeMalformedUrl(url) {
  let normalizedUrl;

  try {
    // Handles URLs starting with special characters
    // from malformed sources, e.g.,
    // "://www.cisco.com/c/en/us/products/.../datasheet-c78-741988.html"
    const wipUrl = url.replace(/^([^a-zA-Z0-9])*/, "");
    normalizedUrl = normalizeUrl(wipUrl);
  } catch (_) {
    console.warn(`URL: not normalized: "${url}"`);
  }

  return normalizedUrl;
}

const logger = require("./logger");

module.exports = {
  getDefaultValue,
  getDomain,
  logger,
  normalizeUrl: _normalizeMalformedUrl,
};
