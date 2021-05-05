const SalesforceError = require("./error");

class SalesforceLoginError extends SalesforceError {
  constructor(message) {
    super(message);
  }
}

module.exports = SalesforceLoginError;
