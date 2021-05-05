const SALESFORCE_DEFAULT_URL = "https://salesforce.com";

module.exports = {
  SALESFORCE_CONNECTION_URL:
    process.env.SALESFORCE_CONNECTION_URL || SALESFORCE_DEFAULT_URL,
  SALESFORCE_URL: process.env.SALESFORCE_URL || SALESFORCE_DEFAULT_URL,
};
