const EventEmitter = require("events");

const { SALESFORCE_CONNECTION_URL } = require("./config");
class SalesforceAdapter extends EventEmitter {
  constructor(username, password, url = SALESFORCE_CONNECTION_URL) {
    super();
    this.connection = { username, password, url };
  }
}

module.exports = SalesforceAdapter;
