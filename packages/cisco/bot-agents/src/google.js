const path = require("path");

const { DEFAULTS } = require("./config");

const COMMAND_SCOPE = "gcloud alpha dialogflow agent";

class GoogleConversationalAgent {
  /**
   * Options for downloading & uploading conversational agents
   * @typedef {Object} CommandOptions
   * @param {String} projectId - the project ID
   * @param {String} dirPath - the directory path on the file system
   * @param {String} agentFileName - the agent's name on the file system, e.g., agent.zip
   * @param {String} account - service account to use with this command
   */

  static getDownloadCommand(options = {}) {
    const {
      projectId,
      dirPath: downloadsDirPath = DEFAULTS.DOWNLOADS_DIR,
      agentFileName = DEFAULTS.AGENT_FILE_NAME,
      account,
    } = options;
    const commandOptions = [
      account ? `--account=${account}` : undefined,
      `--destination=${path.join(downloadsDirPath, agentFileName)}`,
      projectId ? `--project=${projectId}` : undefined,
    ]
      .filter(Boolean)
      .join(" ");

    return `${COMMAND_SCOPE} export ${commandOptions}`;
  }

  static getUploadCommand(options = {}) {
    const {
      projectId,
      dirPath: releasesDirPath = DEFAULTS.RELEASES_DIR,
      agentFileName = DEFAULTS.AGENT_FILE_NAME,
      account,
    } = options;
    const commandOptions = [
      account ? `--account=${account}` : undefined,
      `--source=${path.join(releasesDirPath, agentFileName)}`,
      projectId ? `--project=${projectId}` : undefined,
    ]
      .filter(Boolean)
      .join(" ");

    return `${COMMAND_SCOPE} import ${commandOptions}`;
  }
}

module.exports = GoogleConversationalAgent;
