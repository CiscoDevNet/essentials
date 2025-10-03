/**
 * @file A release specific to Google Cloud.
 * @author Matt Norris <matnorri@cisco.com>
 */

const debug = require("debug")("releases:google");

const colors = require("colors/safe");
const { execSync } = require("child_process");
const path = require("path");

const Release = require("../release");

const {
  APP_FILE,
  EXEC_SYNC_OPTIONS,
  HOSTNAME_BASE,
  HOSTNAME_LOCATION,
} = require("./config");

class GoogleRelease extends Release {
  constructor(projectId, config) {
    super(projectId, config);
    this.projectId = projectId;

    const { location = HOSTNAME_LOCATION } = this.config;

    if (!location) {
      throw new Error("location required to create image.");
    }
    this.location = location;

    debug("initiated");
  }

  get registry() {
    return `${this.location}-${HOSTNAME_BASE}`;
  }

  get fullImageName() {
    return path.join(
      this.registry,
      this.projectId,
      this.project,
      this.imageName
    );
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
    console.log("Creating Deployment configuration...");
    debug("getting environment variables...");
    debug(
      `found ${Object.values(this.envVariables).length} environment variables`
    );
    const fileContent = {
      runtime: "custom",
      env: "flex",
      env_variables: this.envVariables,
    };

    const deploymentPath = path.join(this.releasesDir, APP_FILE);
    Release.write(fileContent, deploymentPath);

    console.log(colors.green("Created Deployment configuration.\n"));
    console.log("You can now deploy this configuration.\n");
  }

  async release() {
    const deploymentPath = path.join(this.releasesDir, APP_FILE);

    // Google versions don't accept dots, only dashes.
    const version = this.version.replace(/\./g, "-");

    const commandParts = [
      "gcloud",
      "app",
      `deploy ${deploymentPath}`,
      `--image-url ${this.fullImageName}`,
      `--project ${this.projectId}`,
      `--version ${version}`,
      "--quiet",
    ];

    const releaseCommand = commandParts.join(" ");
    debug("release command:", releaseCommand);

    execSync(releaseCommand, EXEC_SYNC_OPTIONS);
  }
}

module.exports = GoogleRelease;
