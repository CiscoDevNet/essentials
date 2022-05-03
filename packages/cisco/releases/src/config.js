/**
 * @file Configuration file for releases.
 * @author Matt Norris <matnorri@cisco.com>
 */

const debug = require("debug")("releases:config");

const dotenv = require("dotenv");
const { Env } = require("@humanwhocodes/env");
const fs = require("fs");
const path = require("path");

const { NODE_ENV_DEVELOPMENT, YAML_FILE_EXT } = require("./constants");

const DEFAULT_PLATFORM = {
  NAME: "docker",
  REGISTRY: "docker.io",
  PROJECT: "library",
};

const env = new Env();

const LIFECYCLE = env.first(["LIFECYCLE", "NODE_ENV"], NODE_ENV_DEVELOPMENT);

const currentDir = process.cwd();
let envFilePath = path.join(currentDir, `.env.${LIFECYCLE}`);

// Get the .env file path.
const DEFAULT_ENV_FILE_NAME = ".env";
const isInDevelopment = LIFECYCLE === NODE_ENV_DEVELOPMENT;
const isNoSpecificEnvFile = !fs.existsSync(envFilePath);

if (isInDevelopment && isNoSpecificEnvFile) {
  envFilePath = path.join(currentDir, DEFAULT_ENV_FILE_NAME);
}

// Load the .env file.
debug(`env file: ${envFilePath}`);
const ENVIRONMENT_VARIABLES = dotenv.config({ path: envFilePath });

/**
 * Local releases directory.
 * This is temporary directory to store configuration YAML files, etc.
 * @type {String}
 */
const DEFAULT_RELEASES_DIRECTORY = path.join(currentDir, ".releases");
const RELEASES_DIRECTORY = env.get(
  "RELEASES_DIRECTORY",
  DEFAULT_RELEASES_DIRECTORY
);

const PLATFORM = env.first(
  ["CISCO_RELEASES_PLATFORM", "RELEASES_PLATFORM"],
  DEFAULT_PLATFORM.NAME
);
const REGISTRY = env.first(
  ["CISCO_RELEASES_HOSTNAME", "RELEASES_HOSTNAME"],
  DEFAULT_PLATFORM.REGISTRY
);
const PROJECT = env.first(
  ["CISCO_RELEASES_ORG", "RELEASES_ORG"],
  DEFAULT_PLATFORM.PROJECT
);

const imageNamespace = path.join(REGISTRY, PROJECT);
debug("image namespace:", imageNamespace);

const SERVICE_NAME = "service";
const defaultPackageName = env.get("npm_package_name", SERVICE_NAME);
const packageName = env.first(
  ["CISCO_RELEASES_NAME", "BOT_NAME"],
  defaultPackageName
);
const NAME = path.basename(packageName);

const version = env.get("npm_package_version", "0.0.0");
const VERSION = env.first(["CISCO_RELEASES_VERSION", "BOT_VERSION"], version);

const TEMPLATE_SUFFIX = "-template";

// Configure deployment file names.
const DEPLOYMENT_NAME = "deployment";
const DEPLOYMENT = `${DEPLOYMENT_NAME}.${YAML_FILE_EXT}`;
const DEPLOYMENT_TEMPLATE = `${DEPLOYMENT_NAME}${TEMPLATE_SUFFIX}.${YAML_FILE_EXT}`;

// Configure route file names.
const ROUTE_NAME = "route";
const ROUTE = `${ROUTE_NAME}.${YAML_FILE_EXT}`;
const ROUTE_TEMPLATE = `${ROUTE_NAME}${TEMPLATE_SUFFIX}.${YAML_FILE_EXT}`;

// Configure secret file names.
const SECRET_NAME = "secret";
const DEFAULT_SECRET = `${SECRET_NAME}.${YAML_FILE_EXT}`;
const SECRET = env.get(
  "CONFIG_CISCO_CONTAINER_IMAGE_PULL_SECRET_PATH",
  DEFAULT_SECRET
);

// Configure service file names.
const SERVICE = `${SERVICE_NAME}.${YAML_FILE_EXT}`;
const SERVICE_TEMPLATE = `${SERVICE_NAME}${TEMPLATE_SUFFIX}.${YAML_FILE_EXT}`;

module.exports = {
  env,

  NAME,
  VERSION,

  ENVIRONMENT_VARIABLES,
  LIFECYCLE,
  PORT: env.get("PORT", 3000),

  NPM_REGISTRY: env.get("NPM_REGISTRY", "https://registry.npmjs.org"),
  NPM_USERNAME: env.get("NPM_USERNAME"),
  NPM_PASSWORD: env.get("NPM_PASSWORD"),

  RELEASES_DIRECTORY,
  DEPLOYMENT,
  DEPLOYMENT_TEMPLATE,

  ROUTE,
  ROUTE_TEMPLATE,

  SECRET,
  SERVICE,
  SERVICE_TEMPLATE,

  PLATFORM,
  REGISTRY,
  PROJECT,
};
