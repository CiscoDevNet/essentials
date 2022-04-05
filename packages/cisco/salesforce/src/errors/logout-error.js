const SalesforceError = require("./error");

class SalesforceLogoutError extends SalesforceError {
  constructor(message) {
    super(message);
  }
}

module.exports = SalesforceLogoutError;
