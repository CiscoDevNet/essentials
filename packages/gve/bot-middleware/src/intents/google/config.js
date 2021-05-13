const debug = require("debug")("middleware:intents");

var fs = require("fs");

const { CredentialsError } = require("./errors");
const { env } = require("../../config");

const GOOGLE_APPLICATION_CREDENTIALS = env.require(
  "GOOGLE_APPLICATION_CREDENTIALS"
);

const CREDENTIALS = parseCredentials(GOOGLE_APPLICATION_CREDENTIALS);

/**
 * A Google Auth CredentialBody
 * @typedef {Object} CredentialBody
 * @property client_email
 * @property private_key
 * @see https://github.com/googleapis/google-auth-library-nodejs/blob/9ae2d30c15c9bce3cae70ccbe6e227c096005695/src/auth/credentials.ts#L81
 */

/**
 * Parses the credentials
 * @param {String} credentials - file path or JSON string containing credentials
 * @returns {CredentialBody} credentials needed to authorize
 */
function parseCredentials(credentials) {
  let credentialsSource = credentials;
  const credentialsPath = fs.statSync(credentials);

  try {
    if (credentialsPath.isFile()) {
      debug(`valid filepath: ${credentials}`);
      credentialsSource = fs.readFileSync(credentials, "utf8");
    }
    const { client_email, private_key } = JSON.parse(credentialsSource);
    return { client_email, private_key };
  } catch (error) {
    throw new CredentialsError(error.message);
  }
}

module.exports = {
  CREDENTIALS,
  GOOGLE_APPLICATION_CREDENTIALS,
};
