/**
 * @file A release is used to manage container images.
 * @author Matt Norris <matnorri@cisco.com>
 */

const debug = require("debug")("releases");

const colors = require("colors/safe");
const EventEmitter = require("events");
const { execSync, spawn: nodeSpawn } = require("child_process");
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
  COMMAND_EVENTS,
  DOCKER_COMPOSE_ORIG,
  DOCKER_COMPOSE_CLI,
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
  isBuildKitEnabled: true,
};

const ENV_DEV_MODIFIER = "--test";
const ENV_PRODUCTION = "production";
const ENV_STAGING = "staging";

class Release extends EventEmitter {
  constructor(config = DEFAULT_CONFIG) {
    /**
     * hostName cannot be configured by default.
     * Subclasses may require a particular hostName structure,
     * so the default hostName must be fetched when asked for.
     */

    const {
      name = BOT_NAME,
      environment = NODE_ENV,
      org = RELEASES_ORG,
      version = BOT_VERSION,
      releaseDir = RELEASES_DIRECTORY,
      isBuildKitEnabled = true,
    } = config;
    super();
    this.config = config;
    this.environment = environment;
    this.name = name;
    this.org = org;
    this.version = version;
    this.releasesDir = releaseDir;
    this.isBuildKitEnabled = isBuildKitEnabled;
  }

  set hostName(name) {
    this._hostName = name;
  }

  get hostName() {
    return this._hostName || DEFAULT_CONFIG.hostName;
  }

  get envVariables() {
    const isLoaded = !ENVIRONMENT_VARIABLES.error;
    let otherEnvVars = {};
    if (isLoaded) {
      otherEnvVars = ENVIRONMENT_VARIABLES.parsed;
    } else {
      this.emit(
        "warn",
        "Environment variables not loaded.",
        ENVIRONMENT_VARIABLES.error
      );
    }

    const releaseVars = {
      BOT_NAME: this.name,
      BOT_VERSION: this.version,
      NODE_ENV: this.environment,
    };

    return { ...releaseVars, ...otherEnvVars };
  }

  get imageName() {
    const isDev =
      this.environment !== ENV_PRODUCTION && this.environment !== ENV_STAGING;

    const imageType = isDev ? "development" : "production-ready";

    const modifier = isDev ? ENV_DEV_MODIFIER : "";
    const tag = `${this.version}${modifier}`;
    const imageName = `${this.name}:${tag}`;

    debug(
      `${this.environment} environment produces a ${imageType} image: ${imageName}`
    );

    return imageName;
  }

  get fullImageName() {
    return path.join(this.hostName, this.org, this.imageName);
  }

  /**
   * Returns the Docker command to remove all stopped containers.
   * @returns {String} command to remove all stopped containers
   * @see https://docs.docker.com/engine/reference/commandline/rm/#remove-all-stopped-containers
   */
  static get removeStoppedContainersCommand() {
    return "docker rm $(docker ps --filter status=exited -q) || true";
  }

  /**
   * Returns the command to remove containers with this image.
   * @returns {String} command to remove containers with this image
   * @see https://linuxconfig.org/remove-all-containners-based-on-docker-image-name
   */
  get removeContainerCommand() {
    const commands = [
      "docker ps -a",
      "awk '{ print $1,$2 }'",
      `grep ${this.fullImageName}`,
      "awk '{print $1 }'",
      "xargs -I {} docker rm --force --volumes {}",
    ];
    const command = commands.join(" | ");
    return command;
  }

  get removeImageCommand() {
    return `docker rmi --force ${this.fullImageName}`;
  }

  build(secret) {
    const commandParts = [
      ...this.commandPrefix,
      secret ? `--secret id=${secret}` : undefined,
      DOCKER_COMPOSE_ORIG,
      ...this.commandFlags,
      "build",
    ].filter(Boolean);
    const command = commandParts.join(" ");

    debug(`Build command: ${command}`);

    execSync(command, EXEC_SYNC_OPTIONS);
    console.log(this.getImageUploadInstructions());
  }

  up(shouldUseComposeCli = true) {
    let command;
    if (shouldUseComposeCli) {
      command = this._getComposeCLICommand();
    } else {
      command = this._getComposeCommand();
    }

    debug(`Use the Compose CLI: ${shouldUseComposeCli}`);
    debug(`Compose command (pretty): ${command.replace(/&&/g, "&& \n")}`);

    execSync(command, EXEC_SYNC_OPTIONS);
  }

  /**
   * Return `docker-compose` command.
   * @see https://stackoverflow.com/a/68598538/154065
   * @see https://docs.docker.com/compose/reference/
   * @returns {String} docker-compose command
   * @private
   */
  _getComposeCommand(shouldUseComposeDown = true) {
    const dockerCommand = [
      ...this.commandPrefix,
      DOCKER_COMPOSE_ORIG,
      ...this.commandFlags,
    ];

    let down;
    if (shouldUseComposeDown) {
      down = [
        ...dockerCommand,
        "down",
        "--rmi all",
        "--volumes",
        "--remove-orphans",
      ];
    } else {
      down = [...dockerCommand, "build", "--force-rm", "--no-cache"];
    }

    const up = [...dockerCommand, "up"];
    const commands = [
      ...down,
      "&&",
      this.removeContainerCommand,
      "&&",
      this.removeImageCommand,
      "&&",
      ...up,
    ];
    return commands.join(" ");
  }

  /**
   * Return `docker compose` command.
   * @returns {String} docker compose command
   * @private
   */
  _getComposeCLICommand(shouldUseComposeDown = true) {
    const dockerCommand = [
      ...this.commandPrefix,
      DOCKER_COMPOSE_CLI,
      ...this.commandFlags,
    ];

    let down = [];
    if (shouldUseComposeDown) {
      down = [
        ...dockerCommand,
        "down",
        "--rmi all",
        "--volumes",
        "--remove-orphans",
        "&&",
      ];
    }

    const up = [
      ...dockerCommand,
      "up",
      "--always-recreate-deps",
      "--build",
      "--force-recreate",
      "--renew-anon-volumes",
    ];

    const commands = [
      ...down,
      this.removeContainerCommand,
      "&&",
      this.removeImageCommand,
      "&&",
      ...up,
    ];
    return commands.join(" ");
  }

  get commandPrefix() {
    let buildKitOption;
    if (this.isBuildKitEnabled) {
      buildKitOption = 1;
    }

    const envVariables = [
      `DOCKER_BUILDKIT=${buildKitOption}`,
      `IMAGE_NAME=${this.fullImageName}`,
    ].filter((envVariable) => envVariable !== undefined);

    return envVariables;
  }

  /**
   * Get NPM registry info.
   * @returns {string[]} npm environment variables
   */
  _getNPMVariables() {
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

    return [`NPM_REGISTRY=${NPM_REGISTRY}`, npmUsername, npmPassword].filter(
      Boolean
    );
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

  /**
   * Runs the given command and its args inside a Promise
   * so it can be unpacked later.
   * @param {String} commandName - the command name
   * @param {string[]} args - the command arguments
   * @see https://stackoverflow.com/a/35896832/154065
   * @returns {Promise} string output
   */
  static spawn(commandName, args) {
    return new Promise((resolve, reject) => {
      let stdoutData = "";
      let stderrData = "";

      // Run the command.
      const command = nodeSpawn(commandName, args);

      // Gather normal output.
      command.stdout.on(COMMAND_EVENTS.DATA, (data) => {
        stdoutData += data;
      });

      // Gather errors.
      command.stderr.on(COMMAND_EVENTS.DATA, (data) => {
        stderrData += data;
      });

      // Reject if there is an error.
      command.on(COMMAND_EVENTS.ERROR, (err) => {
        reject(err);
      });

      // When finished, reject if there are errors. Resolve otherwise.
      command.on(COMMAND_EVENTS.CLOSE, () => {
        if (stderrData) {
          reject(stderrData);
        } else {
          resolve(stdoutData);
        }
      });
    });
  }
}

module.exports = Release;
