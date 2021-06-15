/**
 * @file Configuration options specific to OpenShift.
 * @author Matt Norris <matnorri@cisco.com>
 */

const {
  env,
  BOT_URL,
  COMMAND_EVENTS,
  EXEC_SYNC_OPTIONS,
  PORT,
  RELEASES_DEPLOYMENT,
  RELEASES_DEPLOYMENT_TEMPLATE,
  RELEASES_PROJECT_NAME,
  RELEASES_ROUTE,
  RELEASES_ROUTE_TEMPLATE,
  RELEASES_SECRET,
  RELEASES_SERVICE,
} = require("../config");

const RELEASES_IMAGE_PULL_SECRET = env.require("RELEASES_IMAGE_PULL_SECRET");

module.exports = {
  BOT_URL,
  COMMAND_EVENTS,
  EXEC_SYNC_OPTIONS,
  PORT,
  RELEASES_DEPLOYMENT,
  RELEASES_DEPLOYMENT_TEMPLATE,
  RELEASES_PROJECT_NAME,
  RELEASES_ROUTE,
  RELEASES_ROUTE_TEMPLATE,
  RELEASES_SECRET,
  RELEASES_SERVICE,
  RELEASES_IMAGE_PULL_SECRET,
};