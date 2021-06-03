const debug = require("debug")("middleware:people:webex");

const emailAddresses = require("email-addresses");
const mergeWith = require("lodash.mergewith");
const union = require("lodash.union");

const { CONTACT_TYPES, DOMAINS } = require("./constants");
const { hasAllProps, joinArrays } = require("./shared");

// Properties derived from basic properties
const WEBEX_PROPS = [
  "_cecId",
  "_cecEmail",
  "_contactType",
  "_domain",
  "_roles",
  "_username",
];

/**
 * A Webex user
 *
 * Properties beginning with an underscore denote those
 * not normally in a Botkit Person object.
 *
 * @typedef {Object} WebexPerson
 * @property {String} _cecId -  Cisco Employee Connection ID
 * @property {String} _cecEmail - Cisco Employee Connection email, e.g., cecid@cisco.com
 * @property {String} _contactType - type of contact, e.g., "Cisco" or "Partner"
 * @property {String} _domain - domain name, e.g., cisco.com
 * @property {Array<String>} _roles - user's roles
 */

class WebexPeople {
  constructor(config = {}) {
    const { collection: peopleCollection = new Map() } = config;
    this.people = peopleCollection;

    this.get = this.get.bind(this);
    this._getPerson = this._getPerson.bind(this);
    this._setPerson = this._setPerson.bind(this);

    debug("initialized");
  }

  get size() {
    return this.people.size;
  }

  async _getPerson(personId) {
    let person = this.people.get(personId);
    if (!person) {
      debug(`person not found: ${personId}`);
    } else {
      const propCount = Object.keys(person).length;
      debug(`person found: ${personId} - properties: ${propCount}`);
    }

    return person;
  }

  _setPerson(personId, person) {
    this.people.set(personId, person);
    const propCount = Object.keys(person).length;
    debug(`person set: ${personId} - properties: ${propCount}`);
  }

  async get(bot, message, next) {
    debug("webex person requested");

    const personId = message.personId || message.actorId;
    let person = (await this._getPerson(personId)) || {};

    const hasAllDesiredProps = hasAllProps(person, WEBEX_PROPS);
    if (!hasAllDesiredProps) {
      debug(`fetching Webex properties: ${personId}`);
      const webexPerson = await this._getWebexPerson(message);
      mergeWith(person, webexPerson, joinArrays);
    }

    debug(`setting person: ${personId}`);

    this._setPerson(personId, person);
    message._person = await this._getPerson(personId);

    debug(`people count: ${this.people.size}`);

    next();
  }

  _getWebexPerson(message) {
    let { personEmail: email, _person: person } = message;

    // If someone clicks an old card, the `personEmail` property will not be available.
    // Instead, get it from the current user clicking the card.
    if (!email) {
      const { emails = [] } = person;
      email = emails[0];
    }

    let _cecEmail;
    let _cecId;
    let _contactType = CONTACT_TYPES.PARTNER;
    let _username;
    let domain;

    // Get Cisco details.
    if (email) {
      let username;
      ({ local: username, domain } = emailAddresses.parseOneAddress(email));

      if (domain === DOMAINS.CISCO || domain === DOMAINS.WEBEX_BOT) {
        _cecEmail = email;
        _cecId = username;
        _username = username;
        _contactType = CONTACT_TYPES.CISCO;
      }
    }

    // Merge any existing roles.
    let { _roles: roles } = person;
    const _roles = union(roles, [_contactType.toLowerCase()]);

    return {
      id: person.id,
      _contactType,
      _cecEmail,
      _cecId,
      _domain: domain,
      _primaryEmail: email,
      _roles,
      _username,
    };
  }
}

module.exports = WebexPeople;
