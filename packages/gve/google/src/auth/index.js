const debug = require("debug")("google:auth");

const { auth: googleAuth, GoogleAuth } = require("google-auth-library");
const fs = require("fs");

const { AuthError, CredentialsError } = require("./errors");

const { BEGIN_KEY, END_KEY, DEFAULT_SCOPE } = require("./constants");
const {
  GOOGLE_APPLICATION_CREDENTIALS,
  GOOGLE_CLOUD_PROJECT,
  GVE_GOOGLE_EMAIL,
  GVE_GOOGLE_KEY,
} = require("./config");

/**
 * Google Auth CredentialBody
 * @typedef {Object} CredentialBody
 * @property {String} client_email
 * @property {String} private_key
 * @property {String} project_id - project ID (optional)
 * @see https://github.com/googleapis/google-cloud-node/blob/master/docs/authentication.md#the-config-object
 * @see https://github.com/googleapis/google-auth-library-nodejs/blob/9ae2d30c15c9bce3cae70ccbe6e227c096005695/src/auth/credentials.ts#L81
 */

/**
 * @see https://www.npmjs.com/package/google-auth-library
 */
class Auth {
  constructor(config) {
    const { credentials } = config;
    const { project_id, projectId } = credentials;
    this.credentials = credentials;
    this.projectId = project_id || projectId || GOOGLE_CLOUD_PROJECT;
    Object.assign(config, {
      scopes: DEFAULT_SCOPE,
      project_id: this.projectId,
    });
    this.auth = new GoogleAuth(config);
  }

  async authorize() {
    let token;
    try {
      this.client = await this.auth.getClient();
      ({ token } = await this.client.getAccessToken());
    } catch (error) {
      throw new AuthError(error);
    }

    return token;
  }

  static getClientFromJSON(credentials) {
    return googleAuth.fromJSON(credentials);
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

  static buildCredentials(email, key, projectId) {
    return {
      client_email: email,
      private_key: formatKey(key),
      project_id: projectId,
    };
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
      const { client_email, private_key, project_id } = JSON.parse(
        credentialsSource
      );
      return { client_email, private_key, project_id };
    } catch (error) {
      throw new CredentialsError(error.message);
    }
  }
}

function getCredentialsFromSeparateEnvVariables() {
  const client_email = GVE_GOOGLE_EMAIL;
  const rawPrivateKey = GVE_GOOGLE_KEY;
  const project_id = GOOGLE_CLOUD_PROJECT;
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

  return { client_email, private_key, project_id };
}

function formatKey(key) {
  let formattedKey;

  if (key) {
    const joiner = (joined, next) => `${joined}\n${next}`;
    const parts = key.split("\\n");
    formattedKey = parts.reduce(joiner);

    if (!formattedKey.startsWith(BEGIN_KEY)) {
      formattedKey = `${BEGIN_KEY}${formattedKey}`;
    }
    if (!formattedKey.endsWith(END_KEY)) {
      formattedKey = `${formattedKey}${END_KEY}`;
    }
  }

  return formattedKey;
}

module.exports = Auth;
