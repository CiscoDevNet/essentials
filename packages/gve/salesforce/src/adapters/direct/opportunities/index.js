const debug = require("debug")("commands:opportunities:salesforce");

const axios = require("axios");
const EventEmitter = require("events");
const path = require("path");

const { SALESFORCE_OBJECTS_PATH } = require("../../../config");

const filters = ["AND VDC_OPPTY_FLAG__c = true"];

class Opportunities extends EventEmitter {
  constructor(salesforce) {
    super();
    this.salesforce = salesforce;
    this.update = async (id, data) => await this._updateOpportunity(id, data);
    debug("opportunities: initiated");
  }

  async get(opportunityId) {
    const requestUrl = this.getUrl(opportunityId);
    const { headers } = this.salesforce;

    let opportunity;
    try {
      ({ data: opportunity } = await axios.get(requestUrl, { headers }));
    } catch (error) {
      const { status } = error.response;
      // If we get a 404, try to search for Deal ID.
      if (status === 404) {
        debug(
          `Opportunity ${opportunityId} not found. Trying Deal ${opportunityId}...`
        );
        return await this.getByDealId(opportunityId);
      } else {
        this.emit("error", error);
      }
    }
    debug(opportunity);
    return opportunity;
  }

  getUrl(id) {
    const { connection } = this.salesforce;
    const urlPath = path.join(SALESFORCE_OBJECTS_PATH, "Opportunity", id);
    const url = new URL(urlPath, connection.url).toString() + "/";
    debug(`URL: ${url}`);

    return url;
  }

  async getByDealId(dealId) {
    const fields = [
      "Name",
      "Id",
      "DealID__c",
      "VDC_Opportunity_Manager__c",

      // Stage
      "StageName",
      "Forecast_Status__c",
      "Lost_Cancelled_Reason__c",
    ];

    // Salesforce requires spaces to be converted to pluses.
    const spacer = "+";
    const queryParts = [
      `SELECT ${fields.join(`,${spacer}`)}`,
      "FROM Opportunity",
      `WHERE DealID__c='${dealId}'`,
    ].concat(filters);
    const query = queryParts.join(spacer).replace(/ /g, spacer);

    const { headers, connection } = this.salesforce;
    const requestUrl = new URL(`?q=${query}`, connection.url);

    let opportunity;
    try {
      // Salesforce does not like URL-encoded queries.
      // Construct this URL in a "raw" format.
      // const url = `${requestUrl}/?q=${query}`;
      const response = await axios.get(requestUrl, {
        headers,
      });
      const { records } = response.data;
      debug(`${records.length} Opportunities found`);
      opportunity = records[0];
    } catch (error) {
      this.emit("error", error);
    }

    return opportunity;
  }

  async _updateOpportunity(id, data) {
    return this.salesforce.updateObject("Opportunity", id, data);
  }

  static getUrl(url, path = "") {
    return `${new URL(path, url).toString()}/`;
  }
}

module.exports = Opportunities;
