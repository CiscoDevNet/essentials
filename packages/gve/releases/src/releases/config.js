/**
 * @file Configuration file for releases.
 * @author Matt Norris <matnorri@cisco.com>
 */

const {
  env,
  BOT_URL,
  PORT,
  DEPLOYMENT,
  DEPLOYMENT_TEMPLATE,
  ROUTE,
  ROUTE_TEMPLATE,
  SECRET,
  SERVICE,
} = require("../config");

const { COMMAND_EVENTS, EXEC_SYNC_OPTIONS } = require("../constants");

module.exports = {
  env,
  BOT_URL,
  COMMAND_EVENTS,
  EXEC_SYNC_OPTIONS,
  PORT,
  DEPLOYMENT,
  DEPLOYMENT_TEMPLATE,
  ROUTE,
  ROUTE_TEMPLATE,
  SECRET,
  SERVICE,
};
