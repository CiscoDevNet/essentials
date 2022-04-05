const debug = require("debug")("salesforce:users");

class Users {
  constructor(salesforce) {
    this.salesforce = salesforce;
    this.get = async (id) => await this._get(id);
    debug("users: initiated");
  }

  async _get(id) {
    return await this.salesforce.getObject("User", { id });
  }
}

module.exports = Users;
