const debug = require("debug")("salesforce:adapter:direct");

const jsforce = require("jsforce");

const SalesforceAdapter = require("../salesforce");
const { SalesforceLoginError } = require("../../errors");

const Cases = require("./cases");
const Opportunities = require("./opportunities");
const Users = require("./users");

class DirectAdapter extends SalesforceAdapter {
  constructor(username, password, url) {
    super(username, password, url);

    const connector = new jsforce.Connection({
      loginUrl: this.connection.url,
    });
    Object.assign(this.connection, { connector });

    this.Cases = Cases;
    this.Opportunities = Opportunities;
    this.Users = Users;

    debug("initiated");
  }

  /**
   * Get auth token from Salesforce, has to to be invoked before sending requests
   */
  async login() {
    if (!this.connected) {
      let user;
      let loginError;
      const { username, password, connector } = this.connection;
      try {
        if (!username || !password) {
          throw new SalesforceLoginError("Falsy username or password");
        }
        user = await connector.login(username, password);
      } catch (error) {
        loginError = new SalesforceLoginError(error.message);
      }

      if (user) {
        const { accessToken } = connector;
        Object.assign(this.user, user, { accessToken });
        this.connected = !!accessToken;
      }

      const payload = { success: this.connected, user: this.user };
      const errorMessage = loginError ? `: ${loginError.message}` : "";
      debug(`login: salesforce: ${payload.success}${errorMessage}`);

      if (loginError) {
        throw loginError;
      }
    }

    return this.user;
  }

  async logout() {
    return new Promise(() => "Not implemented");
  }
}

module.exports = DirectAdapter;
