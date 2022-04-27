const { execSync } = require("child_process");

const COMMAND = "docker compose";
const EXEC_SYNC_OPTIONS = { stdio: "inherit" };

const DEFAULT_REGISTRY = "docker.io";
const DEFAULT_PROJECT = "library";

class Image {
  constructor(name, options = {}) {
    this.name = name;
    this.options = options;
  }

  get addressableName() {
    // Looks like this:
    // docker.io/library/name:0.0.0
    // Source: https://github.com/opencontainers/.github/blob/master/docs/docs/introduction/digests.md

    const {
      registry = DEFAULT_REGISTRY,
      project = DEFAULT_PROJECT,
      tag,
    } = this.options;

    const colonTag = tag ? `:${tag}` : "";
    const imageName = `${this.name}${colonTag}`;

    const imagePathParts = [registry, project, imageName].filter(Boolean);
    return imagePathParts.join("/");
  }

  build() {
    execSync(this.buildCommand, EXEC_SYNC_OPTIONS);
  }

  run(serviceName = this.name) {
    execSync(this.getRunCommand(serviceName), EXEC_SYNC_OPTIONS);
  }

  get buildCommand() {
    const commandParts = [...this._getBaseCommand(), "build"];
    return commandParts.join(" ");
  }

  getRunCommand(serviceName = this.name) {
    const commandParts = [...this._getBaseCommand(), "run", serviceName];
    return commandParts.join(" ");
  }

  _getBaseCommand() {
    return [COMMAND, ...this._getFileFlags()];
  }

  _getEnvVars() {
    const { imageVar = "IMAGE" } = this.options;
    return `${imageVar}=${this.addressableName}`;
  }

  _getFileFlags() {
    const { files = [] } = this.options;
    return files.map((fileName) => `-f ${fileName}`);
  }
}

module.exports = Image;
