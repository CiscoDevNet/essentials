class SalesforceError extends Error {
  /**
   * @constructs SalesforceError
   * @param {String} message error message
   */
  constructor(message) {
    super(message);
  }
}

module.exports = SalesforceError;
