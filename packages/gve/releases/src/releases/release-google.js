/**
 * @file A release specific to Google Cloud.
 * @author Matt Norris <matnorri@cisco.com>
 */

const debug = require("debug")("releases:google");

const colors = require("colors/safe");
const fs = require("fs");
const path = require("path");
const pick = require("lodash.pick");
const yaml = require("js-yaml");

const Release = require("./release");

const APP_FILE = "app.yml";
const HOSTNAME_BASE = "docker.pkg.dev";

class GoogleRelease extends Release {
  constructor(config) {
    super(config);

    const { location, projectId, projectName } = this.config;
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
