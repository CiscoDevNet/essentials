/**
 * @file Deployment configuration error
 * @author Matt Norris <matnorri@cisco.com>
 */

class DeploymentConfigError extends Error {
  /**
   * @constructs DeploymentConfigError
   * @param {String} message error message
   */
  constructor(message) {
    super(message);
  }
}

module.exports = DeploymentConfigError;
