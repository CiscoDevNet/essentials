const debug = require("debug")("modules:salesforce:cases");

const axios = require("axios");
const path = require("path");
const nodeUrl = require("url");

const { SALESFORCE_OBJECTS_PATH } = require("../../../config");

const CASE = "Case";
const CASE_PATH = path.join(SALESFORCE_OBJECTS_PATH, CASE);

class Cases {
  constructor(salesforce) {
    this.salesforce = salesforce;

    this.create = async (data) =>
      await this.salesforce.retry(this._create.bind(this), data);
    this.describe = async () =>
      await this.salesforce.retry(this._describe.bind(this));
    this.get = async (data) =>
      await this.salesforce.retry(this._get.bind(this), data);
    this.update = async (id, data) =>
      await this.salesforce.updateObject(CASE, id, data);

    debug("cases: initiated");
  }

  /**
   * Sends post request to salesforce
   * @param data - case data
   */
  async _create(data) {
    const { headers: requestHeaders, url, user } = this.salesforce;
    const requestUrl = nodeUrl.resolve(url, CASE_PATH);
    const headers = requestHeaders(user.accessToken);
    return await axios.post(requestUrl, data, { headers });
  }

  async _describe() {
    const pathname = path.join(CASE_PATH, "describe");
    const { headers: requestHeaders, url, user } = this.salesforce;
    const requestUrl = nodeUrl.resolve(url, pathname);
    const headers = requestHeaders(user.accessToken);

    return await axios.get(requestUrl, { headers });
  }

  async _get(id) {
    const pathname = path.join(CASE_PATH, id);
    const { headers: requestHeaders, url, user } = this.salesforce;
    const requestUrl = nodeUrl.resolve(url, pathname);
    const headers = requestHeaders(user.accessToken);

    return await axios.get(requestUrl, { headers });
  }

  async _search(data) {
    const fields = Object.keys(data);
    if (fields.length !== 1) {
      throw Error("salesforce: must have only one query field");
    }

    const field = fields[0];
    let pathname = path.join(CASE_PATH, field, data[field]);
    if (field === "id") {
      pathname = path.join(CASE_PATH, data[field]);
    }

    const { headers: requestHeaders, url, user } = this.salesforce;
    const requestUrl = nodeUrl.resolve(url, pathname);
    const headers = requestHeaders(user.accessToken);

    return await axios.get(requestUrl, { headers });
  }
}

module.exports = Cases;
