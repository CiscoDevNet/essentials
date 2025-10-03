/**
 * @file Configuration file for releases.
 * @author Matt Norris <matnorri@cisco.com>
 */

const {
  env,
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
  COMMAND_EVENTS,
  EXEC_SYNC_OPTIONS,
  DEPLOYMENT,
  DEPLOYMENT_TEMPLATE,
  ROUTE,
  ROUTE_TEMPLATE,
  SECRET,
  SERVICE,
};
