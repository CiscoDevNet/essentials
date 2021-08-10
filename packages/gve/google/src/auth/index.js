const debug = require("debug")("google:auth");

const { CredentialsError } = require("./errors");
var fs = require("fs");

const { BEGIN_KEY, END_KEY } = require("./constants");
const {
  GOOGLE_APPLICATION_CREDENTIALS,
  GOOGLE_EMAIL,
  GOOGLE_KEY,
} = require("./config");

/**
 * Gets the Google credentials from environment variables.
 * @returns {CredentialBody} credentials
 */
function getCredentials() {
  let credentials;

  if (GOOGLE_APPLICATION_CREDENTIALS) {
    credentials = parseCredentials(GOOGLE_APPLICATION_CREDENTIALS);
  } else {
    const client_email = GOOGLE_EMAIL;
    const rawPrivateKey = GOOGLE_KEY;
    let private_key;
    if (rawPrivateKey) {
      private_key = formatKey(rawPrivateKey);
    }
    credentials = { client_email, private_key };
  }

  return credentials;
}

/**
 * A Google Auth CredentialBody
 * @typedef {Object} CredentialBody
 * @property client_email
 * @property private_key
 * @see https://github.com/googleapis/google-cloud-node/blob/master/docs/authentication.md#the-config-object
 * @see https://github.com/googleapis/google-auth-library-nodejs/blob/9ae2d30c15c9bce3cae70ccbe6e227c096005695/src/auth/credentials.ts#L81
 */

/**
 * Parses the credentials
 * @param {String} credentials - file path or JSON string containing credentials
 * @returns {CredentialBody} credentials needed to authorize
 */
function parseCredentials(credentials) {
  let isFile = false;
  let credentialsSource;
  let credentialsPath;

  try {
    credentialsPath = fs.statSync(credentials);
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

module.exports = {
  credentials: getCredentials(),
};
