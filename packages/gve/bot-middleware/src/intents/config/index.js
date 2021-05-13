const debug = require("debug")("middleware:intents");

const { CredentialsError } = require("./errors");
const { env } = require("../../config");
var fs = require("fs");

const GOOGLE_APPLICATION_CREDENTIALS_NAME = "GOOGLE_APPLICATION_CREDENTIALS";
const INTENT_CONFIDENCE = env.get("INTENT_CONFIDENCE", 0.5);

const BEGIN_KEY = "-----BEGIN PRIVATE KEY-----\n";
const END_KEY = "\n-----END PRIVATE KEY-----\n";

let CREDENTIALS;
let GOOGLE_APPLICATION_CREDENTIALS;

try {
  GOOGLE_APPLICATION_CREDENTIALS = env.require(
    GOOGLE_APPLICATION_CREDENTIALS_NAME
  );
  CREDENTIALS = parseCredentials(GOOGLE_APPLICATION_CREDENTIALS);
  debug("credentials loaded:", GOOGLE_APPLICATION_CREDENTIALS_NAME);
} catch (_) {
  const client_email = env.require("INTENT_API_EMAIL");
  const rawPrivateKey = env.require("INTENT_API_KEY");
  debug(process.env.INTENT_API_KEY);
  debug(rawPrivateKey);
  const private_key = formatKey(rawPrivateKey);
  CREDENTIALS = { client_email, private_key };
  debug("credentials loaded: individual");
}

debug("credentials:", CREDENTIALS);

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

function formatKey(key) {
  const parts = key.split("\\n");
  debug(parts);

  const joiner = (joined, next) => `${joined}\n${next}`;
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
  CREDENTIALS,
  INTENT_CONFIDENCE,
};
