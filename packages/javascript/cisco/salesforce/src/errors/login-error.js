const SalesforceError = require("./error");

class SalesforceLoginError extends SalesforceError {
  constructor(error) {
    super(error?.message || error);
    const { code: errorCode, errno: errorNumber, hostname: hostName } = error;
    this.errorCode = errorCode;
    this.errorNumber = errorNumber;
    this.hostName = hostName;
  }

  get suggestedMessage() {
    let solution;
    if (this.errorCode === "ENOTFOUND") {
      solution =
        "The host address could not be found. Connect to VPN and try again.";
    }

    const messageParts = [
      `Salesforce not connected. Tried to connect to ${
        this.hostName || "an unknown host"
      }.`,
      `Returned error code ${this.errorNumber || "unknown"} - ${
        this.errorCode || "unknown"
      }.`,
      solution,
    ];

    return messageParts.join(" ").trim();
  }
}

module.exports = SalesforceLoginError;
