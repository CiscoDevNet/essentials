/**
 * @file A release specific to Google Cloud.
 * @author Matt Norris <matnorri@cisco.com>
 */

const debug = require("debug")("releases:google");

const colors = require("colors/safe");
const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const pick = require("lodash.pick");
const yaml = require("js-yaml");

const Release = require("../release");

const {
  APP_FILE,
  EXEC_SYNC_OPTIONS,
  HOSTNAME_BASE,
  HOSTNAME_LOCATION,
  PROJECT_ID,
  PROJECT_NAME,
} = require("./config");

class GoogleRelease extends Release {
  constructor(config) {
    super(config);

    const {
      location = HOSTNAME_LOCATION,
      projectId = PROJECT_ID,
      projectName = PROJECT_NAME,
    } = this.config;
    if (!projectId && !projectName) {
      throw new Error("projectId or projectName needed to create image.");
    }
    this.projectId = projectId || projectName;

    if (!location) {
      throw new Error("location needed to create image.");
    }
    this.location = location;

    debug("initiated");
  }

  get hostName() {
    return `${this.location}-${HOSTNAME_BASE}`;
  }

  get imageRepo() {
    return path.join(this.hostName, this.projectId, this.org, this.imageName);
  }

  activate() {
    execSync(`gcloud config set project ${this.projectId}`, EXEC_SYNC_OPTIONS);
    execSync(
      `gcloud config set compute/region ${this.location}`,
      EXEC_SYNC_OPTIONS
    );
    console.log(colors.green(`Project activated: ${this.projectId}`));
    return this.projectId;
  }

  buildDeployment() {
    const releasesDir = Release.createReleasesDir();

    // Include any valid environment variables in the deployment configuration.
    const env_variables = pick(process.env, this.envVariables);

    const data = {
      runtime: "custom",
      env: "flex",
      env_variables,
    };

    const deployment = path.join(releasesDir, APP_FILE);
    const yamlData = yaml.safeDump(data);
    fs.writeFileSync(deployment, yamlData, "utf8");

    // Google versions don't accept dots, only dashes.
    const version = this.version.replace(/\./g, "-");
    const commandParts = [
      "gcloud app deploy",
      deployment,
      "--quiet",
      `--version ${version}`,
    ];
    const command = commandParts.join(" ");
    const instructions = [
      `${colors.green("Created deployment file.")} Deploy it with:`,
      "",
      command,
      "",
    ];

    return { command: commandParts, imageName: this.imageName, instructions };
  }
}

module.exports = GoogleRelease;
