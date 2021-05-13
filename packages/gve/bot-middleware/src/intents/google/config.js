const debug = require("debug")("middleware:intents");

var fs = require("fs");

const { CredentialsError } = require("./errors");
const { env } = require("../../config");

const GOOGLE_APPLICATION_CREDENTIALS = env.require(
  "GOOGLE_APPLICATION_CREDENTIALS"
);

/**
 * Object containing client_email and private_key properties, or the
 * external account client options.
 */

// export interface CredentialBody {
//   client_email?: string;
//   private_key?: string;
// }

// Is this a valid filepath?
// Yes - do nothing OR... read the file and put it into the credential format
// No - take what's there and try to put it into a credential format

const CREDENTIALS = parseCredentials(GOOGLE_APPLICATION_CREDENTIALS);

function parseCredentials(credentials) {
  const credentialsPath = fs.statSync(credentials);
  if (credentialsPath.isFile()) {
    debug(`valid filepath: true: ${credentials}`);
    try {
      const rawFile = fs.readFileSync(credentials, "utf8");
      return JSON.parse(rawFile);
    } catch (error) {
      throw new CredentialsError(error.message);
    }
  } else {
    debug(`valid filepath: false - parsing the string...`);
    return JSON.parse(credentials);
  }
}

module.exports = {
  CREDENTIALS,
  GOOGLE_APPLICATION_CREDENTIALS,
};
