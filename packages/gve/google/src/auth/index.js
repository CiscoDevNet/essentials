const debug = require("debug")("google:auth");

const { auth: googleAuth } = require("google-auth-library");
const fs = require("fs");

const { AuthError, CredentialsError } = require("./errors");

const { BEGIN_KEY, END_KEY } = require("./constants");
const {
  GOOGLE_APPLICATION_CREDENTIALS,
  GVE_GOOGLE_EMAIL,
  GVE_GOOGLE_KEY,
} = require("./config");

/**
 * Google Auth CredentialBody
 * @typedef {Object} CredentialBody
 * @property {String} client_email
 * @property {String} private_key
 * @see https://github.com/googleapis/google-cloud-node/blob/master/docs/authentication.md#the-config-object
 * @see https://github.com/googleapis/google-auth-library-nodejs/blob/9ae2d30c15c9bce3cae70ccbe6e227c096005695/src/auth/credentials.ts#L81
 */

class Auth {
  constructor(config) {
    this.credentials = config.credentials;
    this.client = googleAuth.fromJSON(this.credentials);
    this.client.scopes = "https://www.googleapis.com/auth/cloud-platform";
  }

  async authorize() {
    let token;
    try {
      ({ token } = await this.client.getAccessToken());
    } catch (error) {
      throw new AuthError(error);
    }

    return token;
  }

  /**
   * Gets the authorization credentials.
   * @param {String} credentials - file path or JSON string containing credentials
   * @returns {CredentialBody} credentials
   */
  static getCredentials(credentials = GOOGLE_APPLICATION_CREDENTIALS) {
    let parsedCredentials;
    try {
      parsedCredentials = Auth.parseCredentials(credentials);
    } catch (_) {
      parsedCredentials = getCredentialsFromSeparateEnvVariables();
    }

    return parsedCredentials;
  }

  /**
   * Parses the given credentials.
   * @param {String} credentials - file path or JSON string containing credentials
   * @returns {CredentialBody} credentials needed to authorize
   */
  static parseCredentials(credentials = GOOGLE_APPLICATION_CREDENTIALS) {
    let isFile = false;
    let credentialsSource;

    try {
      const credentialsPath = fs.statSync(credentials);
      isFile = credentialsPath.isFile();
      if (isFile) {
        credentialsSource = fs.readFileSync(credentials, "utf8");
      } else {
        throw new Error("Invalid file path. Use credentials directly.");
      }
    } catch (_) {
      credentialsSource = credentials;
    }

    debug(`valid filepath: ${isFile}: ${credentials}`);

    try {
      const { client_email, private_key } = JSON.parse(credentialsSource);
      return { client_email, private_key };
    } catch (error) {
      throw new CredentialsError(error.message);
    }
  }
}

function getCredentialsFromSeparateEnvVariables() {
  const client_email = GVE_GOOGLE_EMAIL;
  const rawPrivateKey = GVE_GOOGLE_KEY;
  const private_key = formatKey(rawPrivateKey);

  const missingProps = [client_email, private_key].filter(
    (prop) => prop === undefined
  );
  const isMissingProps = !!missingProps.length;

  if (isMissingProps) {
    const missing = missingProps.join(", ");
    throw new CredentialsError(
      `Missing properties: ${missing}. Credentials must include client_email and private_key properties.`
    );
  }

  return { client_email, private_key };
}

function formatKey(key) {
  const joiner = (joined, next) => `${joined}\n${next}`;
  const parts = key.split("\\n");
  let formattedKey = parts.reduce(joiner);

  if (!formattedKey.startsWith(BEGIN_KEY)) {
    formattedKey = `${BEGIN_KEY}${formattedKey}`;
  }
  if (!formattedKey.endsWith(END_KEY)) {
    formattedKey = `${formattedKey}${END_KEY}`;
  }

  return formattedKey;
}

module.exports = Auth;
