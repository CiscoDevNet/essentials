/**
 * @file Configuration options specific to Google.
 * @author Matt Norris <matnorri@cisco.com>
 */

const { env, EXEC_SYNC_OPTIONS } = require("../config");

const APP_FILE = "app.yml";
const HOSTNAME_BASE = "docker.pkg.dev";
const HOSTNAME_LOCATION = env.get(
  "CISCO_RELEASES_HOSTNAME_LOCATION",
  "us-east1"
);

module.exports = {
  APP_FILE,
  EXEC_SYNC_OPTIONS,
  HOSTNAME_BASE,
  HOSTNAME_LOCATION,
};
