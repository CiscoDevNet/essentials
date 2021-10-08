/**
 * @file Common functions for all apps and systems
 * @author Matt Norris <matnorri@cisco.com>
 */

const debug = require("debug")("modules:core");

const forceBoolean = require("force-boolean").default;
const nodeUrl = require("url");
const normalizeUrl = require("normalize-url");

const URL_OPTIONS = { stripWWW: false };

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
  // Handle URLs starting with special characters from malformed sources,
  // e.g., "://www.cisco.com/c/en/us/products/.../datasheet-c78-741988.html"
  const sanitizedUrl = url.replace(/^([^a-zA-Z0-9])*/, "");
  return normalizeUrl(sanitizedUrl, URL_OPTIONS);
}

module.exports = {
  getDefaultValue,
  getDomain,
  normalizeUrl: _normalizeMalformedUrl,
};
