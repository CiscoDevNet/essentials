/**
 * @file Configuration options specific to Google.
 * @author Matt Norris <matnorri@cisco.com>
 */

const {
  env,
  EXEC_SYNC_OPTIONS,
  RELEASES_PROJECT_ID: PROJECT_ID,
  RELEASES_PROJECT_NAME: PROJECT_NAME,
} = require("../config");

const APP_FILE = "app.yml";
const HOSTNAME_BASE = "docker.pkg.dev";
const HOSTNAME_LOCATION = env.get("RELEASES_HOSTNAME_LOCATION", "us-east1");

module.exports = {
  APP_FILE,
  EXEC_SYNC_OPTIONS,
  HOSTNAME_BASE,
  HOSTNAME_LOCATION,
  PROJECT_ID,
  PROJECT_NAME,
};
