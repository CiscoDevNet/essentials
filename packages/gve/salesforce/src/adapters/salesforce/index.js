const debug = require("debug")("salesforce:adapter:base");

const { SALESFORCE_CONNECTION_URL } = require("./config");

class SalesforceAdapter {
  constructor(username, password, url = SALESFORCE_CONNECTION_URL) {
    this.connection = { username, password, url };
    this.user = { username };
    debug("initiated");
  }
}

module.exports = SalesforceAdapter;
