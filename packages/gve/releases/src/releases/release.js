/**
 * @file A release is used to manage container images.
 * @author Matt Norris <matnorri@cisco.com>
 */

const debug = require("debug")("releases");

const colors = require("colors/safe");
const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const yaml = require("js-yaml");

const {
  BOT_NAME,
  BOT_VERSION,
  ENVIRONMENT_VARIABLES,
  NODE_ENV,
  NPM_REGISTRY,
  NPM_USERNAME,
  NPM_PASSWORD,
  RELEASES_DIRECTORY,
  RELEASES_HOSTNAME,
  RELEASES_ORG,
} = require("../config");

const {
  DOCKER_COMPOSE_BUILD_COMMAND,
  DOCKER_COMPOSE_UP_COMMAND,
  EXEC_SYNC_OPTIONS,
  YAML_FILE_EXT,
} = require("../constants");

/**
 * Release configuration
 * @typedef {Object} ReleaseConfig
 * @property {String} releasesDir - path to a releases directory
 */
const DEFAULT_CONFIG = {
  hostName: RELEASES_HOSTNAME,
  name: BOT_NAME,
  environment: NODE_ENV,
  org: RELEASES_ORG,
  version: BOT_VERSION,
  releaseDir: RELEASES_DIRECTORY,
};

const ENV_PROD = "production";
const ENV_NON_PROD_MODIFIER = "--test";

class Release {
  constructor(config = DEFAULT_CONFIG) {
    const {
      hostName = RELEASES_HOSTNAME,
      name = BOT_NAME,
      environment = NODE_ENV,
      org = RELEASES_ORG,
      version = BOT_VERSION,
      releaseDir = RELEASES_DIRECTORY,
    } = config;

    this.config = config;

    this.hostName = hostName;
    this.name = name;
    this.environment = environment;
    this.org = org;
    this.version = version;
    this.releasesDir = releaseDir;

    debug("initiated");
  }

  get envVariables() {
    const hasLoadedEnvVars = !ENVIRONMENT_VARIABLES.error;

    let otherEnvVars = {};
    if (hasLoadedEnvVars) {
      otherEnvVars = ENVIRONMENT_VARIABLES.parsed;
    } else {
      console.warn("Error loading env variables");
    }

    const releaseVars = {
      BOT_NAME: this.name,
      BOT_VERSION: this.version,
      NODE_ENV: this.environment,
    };

    return { ...releaseVars, ...otherEnvVars };
  }

  get imageName() {
    const isNotProd = this.environment !== ENV_PROD;
    const modifier = isNotProd ? ENV_NON_PROD_MODIFIER : "";
    const tag = `${this.version}${modifier}`;
    return `${this.name}:${tag}`;
  }

  get fullImageName() {
    return path.join(this.hostName, this.org, this.imageName);
  }

  build() {
    const commandParts = [
      ...this.commandPrefix,
      DOCKER_COMPOSE_BUILD_COMMAND,
      ...this.commandFlags,
      "build",
    ];
    const command = commandParts.join(" ");
    debug(command);
    execSync(command, EXEC_SYNC_OPTIONS);
    console.log(this.getImageUploadInstructions());
  }

  up() {
    const commandParts = [
      ...this.commandPrefix,
      DOCKER_COMPOSE_UP_COMMAND,
      ...this.commandFlags,
      "up",
      "--force-recreate",
      "--build",
      "--always-recreate-deps",
      "--renew-anon-volumes",
    ];
    const command = commandParts.join(" ");
    debug(command);
    execSync(command, EXEC_SYNC_OPTIONS);
  }

  get commandPrefix() {
    debug(`NPM_REGISTRY: ${NPM_REGISTRY}`);

    let npmUsername;
    let npmPassword;

    if (!NPM_USERNAME) {
      debug(`NPM_USERNAME not set`);
    } else {
      npmUsername = `NPM_USERNAME=${NPM_USERNAME}`;
    }

    if (!NPM_PASSWORD) {
      debug(`NPM_PASSWORD not set`);
    } else {
      npmPassword = `NPM_PASSWORD=${NPM_PASSWORD}`;
    }

    const envVariables = [
      `IMAGE_NAME=${this.fullImageName}`,
      `NPM_REGISTRY=${NPM_REGISTRY}`,
      npmUsername,
      npmPassword,
    ].filter((envVariable) => envVariable !== undefined);

    return envVariables;
  }

  get commandFlags() {
    const dockerComposePrimaryFile = `docker-compose.${YAML_FILE_EXT}`;
    const dockerComposeEnvFile = `docker-compose.${this.environment}.${YAML_FILE_EXT}`;

    return [`-f ${dockerComposePrimaryFile}`, `-f ${dockerComposeEnvFile}`];
  }

  createDir(dirPath) {
    const releaseDir = dirPath || this.releaseDir;
    return Release.createReleasesDir(releaseDir);
  }

  static createReleasesDir(dirPath = RELEASES_DIRECTORY) {
    if (!fs.existsSync(dirPath)) {
      fs.mkdirSync(dirPath);
    }

    return dirPath;
  }

  getImageUploadInstructions() {
    const instructions = [
      `${colors.green("Created image.")} Push it to the registry with:`,
      "",
      `  docker push ${this.fullImageName}`,
      "",
    ];

    return instructions.join("\n");
  }

  /**
   * Reads the given YAML template file. Returns its contents as an object.
   * @param {String} template path to YAML configuration template
   * @returns {Object} template file contents
   */
  static read(template) {
    const fileContents = fs.readFileSync(template, "utf8");
    return yaml.safeLoad(fileContents);
  }

  /**
   * Writes a new YAML configuration file.
   * @param {Object} contents YAML contents to write
   * @param {String} output path to destination file
   */
  static write(contents, output) {
    const yamlData = yaml.safeDump(contents);
    fs.writeFileSync(output, yamlData, "utf8");
  }
}

module.exports = Release;
