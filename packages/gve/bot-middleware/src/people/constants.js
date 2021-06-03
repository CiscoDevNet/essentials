/**
 * A person must have all of these properties defined to be considered "data complete".
 * @type {Array<String>}
 */
const BASIC_PROPS = [
  "id",
  "emails",
  "phoneNumbers",
  "displayName",
  "nickName",
  "firstName",
  "lastName",
  "avatar",
  "orgId",
  "created",
  "type",
];

const CONTACT_TYPES = {
  CISCO: "Cisco",
  PARTNER: "Partner",
};

const DOMAINS = {
  CISCO: "cisco.com",
  WEBEX_BOT: "webex.bot",
};

module.exports = {
  BASIC_PROPS,
  CONTACT_TYPES,
  DOMAINS,
};
