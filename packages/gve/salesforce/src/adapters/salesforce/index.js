const debug = require("debug")("salesforce:adapter:base");

const EventEmitter = require("events");

const { SALESFORCE_CONNECTION_URL } = require("./config");

class SalesforceAdapter extends EventEmitter {
  constructor(username, password, url = SALESFORCE_CONNECTION_URL) {
    super();
    this.connection = { username, password, url };
    this.user = { username };
    super.emit("adapter created", this.connection);
    debug("initiated");
  }
}

module.exports = SalesforceAdapter;
