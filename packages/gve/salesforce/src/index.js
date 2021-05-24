const debug = require("debug")("salesforce");

const axios = require("axios");
const EventEmitter = require("events");
const path = require("path");

const adapters = require("./adapters");
const errors = require("./errors");

const { queryObjectPath } = require("./constants");

/**
 * Salesforce user data.
 *
 * @typedef {Object} SalesforceUser
 * @property {String} id - user ID
 * @property {String} username - username
 * @property {String} accessToken - user's API access token
 * @property {String} organizationId - user's organization ID
 * @property {String} url - full URL after signing in, e.g, https://SUBDOMAIN.my.salesforce.com/id/ORGANIZATION-ID/USER-ID
 */

/**
 * Salesforce controller class
 */
class Salesforce extends EventEmitter {
  /**
   * Create instance of Salesforce controller
   * @param {String} username
   * @param {String} password
   * @param {String} url - Salesforce host address
   */
  constructor(url, adapter) {
    super();
    const {
      username,
      connection,
      login,
      logout,
      Accounts,
      Cases,
      Opportunities,
      Users,
    } = adapter;

    this.url = url;
    this.user = { username };
    this.connection = connection;
    this.connected = false;

    this.login = login.bind(this);
    this.logout = logout.bind(this);
    this.retry = this.retry.bind(this);

    this.accounts = new Accounts(this);
    this.cases = new Cases(this);
    this.opportunities = new Opportunities(this);
    this.users = new Users(this);

    debug("initiated");
  }

  async updateObject(objectName, id, data) {
    const pathname = path.join(queryObjectPath, objectName, id);
    const url = new URL(pathname, this.url).toString() + "/";
    const headers = this.headers(this.user.accessToken);

    // A normal PATCH doesn't seem to work on the Salesforce API.
    // Use POST instead.
    // https://stackoverflow.com/a/53501339/154065
    const params = { _HttpMethod: "PATCH" };

    // Salesforce will err if an ID field is present.
    const body = { ...data };
    delete body.Id;

    return await axios.post(url, body, { headers, params });
  }

  headers(accessToken) {
    return {
      Accept: "application/json;charset=UTF-8",
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      "X-PrettyPrint": "1",
      "Sforce-Auto-Assign": "FALSE",
    };
  }

  async getObject(objectName, data) {
    const fields = Object.keys(data);
    if (fields.length !== 1) {
      throw Error("salesforce: must have only one query field");
    }
    const field = fields[0];
    const fieldPath = field === "id" ? "" : field;
    const objectPath = path.join(
      queryObjectPath,
      objectName,
      fieldPath,
      data[field]
    );
    const requestUrl = new URL(objectPath, this.url).toString() + "/";

    const headers = this.headers(this.user.accessToken);
    const response = await axios.get(requestUrl, { headers });
    return response.data;
  }

  async retry(request, ...args) {
    debug(`retry: attempting: ${request.name}: args: ${args.length}`);
    try {
      return await request(...args);
    } catch (error) {
      const { response } = error;
      const unauthorized = response && response.status === 401;
      if (unauthorized) {
        this.connected = false;
        console.info(
          `salesforce: User is not logged in. Logging in and trying again.`
        );
        await this.login();
        return await request(...args);
      } else {
        throw error;
      }
    }
  }
}

module.exports = { adapters, errors, Salesforce };
