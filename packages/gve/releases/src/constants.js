const YAML_FILE_EXT = "yml";

const COMMAND_EVENTS = { DATA: "data", CLOSE: "close", ERROR: "error" };
const EXEC_SYNC_OPTIONS = { stdio: "inherit" };
const NODE_ENV_DEVELOPMENT = "development";

/**
 * "docker-compose build" command
 *
 * "docker compose" and "docker-compose" are different.
 * Use docker-compose to enable builds with ARGS.
 * @see https://stackoverflow.com/a/67853849/154065
 */
const DOCKER_COMPOSE_BUILD_COMMAND = "docker-compose";

const DOCKER_COMPOSE_UP_COMMAND = "docker compose";

module.exports = {
  COMMAND_EVENTS,
  DOCKER_COMPOSE_BUILD_COMMAND,
  DOCKER_COMPOSE_UP_COMMAND,
  EXEC_SYNC_OPTIONS,
  NODE_ENV_DEVELOPMENT,
  YAML_FILE_EXT,
};
