const debug = require("debug")("middleware:intents");

const { CredentialsError } = require("./errors");
const { env } = require("../../config");
var fs = require("fs");

let GOOGLE_APPLICATION_CREDENTIALS = env.get("GOOGLE_APPLICATION_CREDENTIALS");
const INTENT_CONFIDENCE = env.get("INTENT_CONFIDENCE", 0.5);

const BEGIN_KEY = "-----BEGIN PRIVATE KEY-----\n";
const END_KEY = "\n-----END PRIVATE KEY-----\n";

let CREDENTIALS;

if (GOOGLE_APPLICATION_CREDENTIALS) {
  CREDENTIALS = parseCredentials(GOOGLE_APPLICATION_CREDENTIALS);
} else {
  const client_email = env.get("INTENT_API_EMAIL");
  const rawPrivateKey = env.get("INTENT_API_KEY");
  let private_key;
  if (rawPrivateKey) {
    private_key = formatKey(rawPrivateKey);
  }
  CREDENTIALS = { client_email, private_key };
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
  CREDENTIALS,
  INTENT_CONFIDENCE,
};
