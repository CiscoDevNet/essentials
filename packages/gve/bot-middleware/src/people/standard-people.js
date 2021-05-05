const debug = require("debug")("middleware:people");

const mergeWith = require("lodash.mergewith");
const util = require("util");

const { BASIC_PROPS } = require("./constants");
const { hasAllProps, joinArrays } = require("./shared");

/**
 * Person's phone number.
 *
 * @typedef {Object} PhoneNumber
 * @property {String} type - type of phone number, e.g., work, home
 * @property {String} value - phone number itself, e.g., '+1 555 867 5309'
 */

/**
 * A typical bot user
 *
 * @typedef {Object} Person
 * @property {String} id - Encrypted person ID
 * @property {Array<String>} emails - email addresses
 * @property {Array<PhoneNumber>} phoneNumbers - phone numbers
 * @property {String} displayName - display name
 * @property {String} nickName - nickname
 * @property {String} firstName - first name
 * @property {String} lastName - last name
 * @property {String} avatar - URL of person's avatar at 1600px
 * @property {String} orgId - encrypted organization ID
 * @property {Date} created - date person was created in Webex Teams, e.g., 2014-06-20T20:35:16.172Z
 * @property {String} type - type of user, e.g., "person"
 */

class People {
  constructor(config = {}) {
    /**
     * Known people.
     *
     * Keys are of type {@link Person.id}.
     * Properties are of type {@link Person}.
     * @typedef {Map} People
     */
    const { collection: peopleCollection = new Map() } = config;
    this.people = peopleCollection;

    const { people } = config;
    if (Array.isArray(people)) {
      people.forEach((person) => {
        this.people.set(person.id, person);
        const setPerson = this.people.get(person.id);
        debug(`person set: ${util.inspect(setPerson)}`);
      });
    }

    this.get = this.get.bind(this);
    this._getPerson = this._getPerson.bind(this);
    this._setPerson = this._setPerson.bind(this);

    debug("initialized");
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

  async get(bot, message, next) {
    debug("person requested");

    const personId = message.personId || message.actorId;
    let person = (await this._getPerson(personId)) || {};

    // Fetch any incomplete user data.
    const hasAllDesiredProps = hasAllProps(person, BASIC_PROPS);
    if (!hasAllDesiredProps) {
      debug(`fetching properties: ${personId}`);
      const enhancedPerson = await bot.api.people.get(personId);
      mergeWith(person, enhancedPerson, joinArrays);
      Object.assign(person, enhancedPerson);
    }

    debug(`setting person: ${personId}`);

    this._setPerson(personId, person);
    message._person = await this._getPerson(personId);

    debug(`people count: ${this.people.size}`);

    next();
  }

  _setPerson(personId, person) {
    this.people.set(personId, person);
    const propCount = Object.keys(person).length;
    debug(`person set: ${personId} - properties: ${propCount}`);
  }

  get size() {
    return this.people.size;
  }
}

module.exports = People;
