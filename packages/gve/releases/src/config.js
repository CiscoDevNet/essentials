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
  HOSTNAME: "docker.io",
  ORG: "libary",
};

const env = new Env();

const NODE_ENV = env.get("NODE_ENV", NODE_ENV_DEVELOPMENT);

const currentDir = process.cwd();

let envFilePath = path.join(currentDir, `.env.${NODE_ENV}`);

// Get the .env file path.
const DEFAULT_ENV_FILE_NAME = ".env";
const isInDevelopment = NODE_ENV === NODE_ENV_DEVELOPMENT;
const isNoSpecificEnvFile = !fs.existsSync(envFilePath);

if (isInDevelopment && isNoSpecificEnvFile) {
  envFilePath = path.join(currentDir, DEFAULT_ENV_FILE_NAME);
}

// Load the .env file.
debug(`env file: ${envFilePath}`);
const ENVIRONMENT_VARIABLES = dotenv.config({ path: envFilePath });

/**
 * Release configuration directory.
 * @type {String}
 */
const DEFAULT_RELEASES_DIRECTORY = path.join(currentDir, ".releases");
const RELEASES_DIRECTORY = env.get(
  "RELEASES_DIRECTORY",
  DEFAULT_RELEASES_DIRECTORY
);

const {
  RELEASES_PLATFORM = DEFAULT_PLATFORM.NAME,
  RELEASES_HOSTNAME = DEFAULT_PLATFORM.HOSTNAME,
  RELEASES_ORG = DEFAULT_PLATFORM.ORG,
} = process.env;
const imageNamespace = path.join(RELEASES_HOSTNAME, RELEASES_ORG);
debug("image namespace:", imageNamespace);

const RELEASES_PROJECT_ID = process.env.RELEASES_PROJECT_ID;
const RELEASES_PROJECT_NAME =
  process.env.RELEASES_PROJECT_NAME || RELEASES_PROJECT_ID;

debug("project name:", RELEASES_PROJECT_NAME);

const BOT_NAME =
  process.env.BOT_NAME || path.basename(process.env.npm_package_name || "bot");
const BOT_VERSION =
  process.env.BOT_VERSION || process.env.npm_package_version || "0.0.0";

const TEMPLATE_SUFFIX = "-template";

// Configure deployment file names.
const DEPLOYMENT_NAME = "deployment";
const RELEASES_DEPLOYMENT = `${DEPLOYMENT_NAME}.${YAML_FILE_EXT}`;
const RELEASES_DEPLOYMENT_TEMPLATE = `${DEPLOYMENT_NAME}${TEMPLATE_SUFFIX}.${YAML_FILE_EXT}`;

// Configure route file names.
const ROUTE_NAME = "route";
const RELEASES_ROUTE = `${ROUTE_NAME}.${YAML_FILE_EXT}`;
const RELEASES_ROUTE_TEMPLATE = `${ROUTE_NAME}${TEMPLATE_SUFFIX}.${YAML_FILE_EXT}`;

// Configure secret file names.
const SECRET_NAME = "secret";
const RELEASES_SECRET = `${SECRET_NAME}.${YAML_FILE_EXT}`;

// Configure service file names.
const SERVICE_NAME = "service";
const RELEASES_SERVICE = `${SERVICE_NAME}.${YAML_FILE_EXT}`;

/**
 * The releases deployment URL.
 * @constant {String}
 */
const { RELEASES_URL } = process.env;

module.exports = {
  BOT_NAME,
  BOT_VERSION,
  BOT_URL: process.env.BOT_URL,

  ENVIRONMENT_VARIABLES,
  NODE_ENV,
  PORT: process.env.PORT || 3000,

  NPM_REGISTRY: env.get("NPM_REGISTRY", "https://registry.npmjs.org"),
  NPM_USERNAME: env.get("NPM_USERNAME"),
  NPM_PASSWORD: env.get("NPM_PASSWORD"),

  RELEASES_DIRECTORY,
  RELEASES_DEPLOYMENT,
  RELEASES_DEPLOYMENT_TEMPLATE,

  RELEASES_ROUTE,
  RELEASES_ROUTE_TEMPLATE,

  RELEASES_SECRET,
  RELEASES_SERVICE,

  RELEASES_HOSTNAME,
  RELEASES_ORG,
  RELEASES_PLATFORM,

  RELEASES_IMAGE_PULL_SECRET: process.env.RELEASES_IMAGE_PULL_SECRET,
  RELEASES_PROJECT_ID,
  RELEASES_PROJECT_NAME,

  RELEASES_URL,
};
