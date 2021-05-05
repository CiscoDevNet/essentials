const path = require("path");

const SALESFORCE_DEFAULT_API_VERSION = "51.0";
const SALESFORCE_DEFAULT_URL = "https://salesforce.com";

const SALESFORCE_CONNECTION_URL =
  process.env.SALESFORCE_CONNECTION_URL || SALESFORCE_DEFAULT_URL;
const SALESFORCE_URL = process.env.SALESFORCE_URL || SALESFORCE_DEFAULT_URL;

const SALESFORCE_API_VERSION = formatApiVersion(
  process.env.SALESFORCE_API_VERSION || SALESFORCE_DEFAULT_API_VERSION
);

const SALESFORCE_QUERY_PATH = getQueryPath(SALESFORCE_API_VERSION);
const SALESFORCE_OBJECTS_PATH = getSalesforceObjectsPath(
  SALESFORCE_API_VERSION
);

/**
 * Formats the given version number, e.g., "51.0".
 * @param {String|number} version API version number
 * @returns formatted API version number
 */
function formatApiVersion(version) {
  return String(parseFloat(version).toFixed(1));
}

/**
 * Returns the query path, e.g., "services/data/v51.0/query".
 * @param {String} version formatted API version number
 * @returns the Salesforce query path
 */
function getQueryPath(version) {
  const servicesPath = getServicesPath(version);
  return path.join(servicesPath, "query");
}

/**
 * Returns the Salesforce objects path, e.g., "services/data/v51.0/sobjects".
 * @param {String} version formatted API version number
 * @returns the Salesforce objects path
 */
function getSalesforceObjectsPath(version) {
  const servicesPath = getServicesPath(version);
  return path.join(servicesPath, "sobjects");
}

/**
 * Returns the services path, e.g., "services/data/v44.0"
 * @param {String} version formatted API version number
 * @returns the services path
 */
function getServicesPath(version) {
  return path.join("services", "data", `v${version}`);
}

module.exports = {
  SALESFORCE_CONNECTION_URL,
  SALESFORCE_URL,
  SALESFORCE_API_VERSION,
  SALESFORCE_OBJECTS_PATH,
  SALESFORCE_QUERY_PATH,
};
