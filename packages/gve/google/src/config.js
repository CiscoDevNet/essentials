const { Env } = require("@humanwhocodes/env");
const env = new Env();

const GOOGLE_CLOUD_PROJECT = getProjectId();

/**
 * @see https://github.com/googleapis/google-auth-library-nodejs/blob/1ca3b733427d951ed624e1129fca510d84d5d0fe/src/auth/googleauth.ts#L646
 * @returns
 */
function getProjectId() {
  return (
    env.get("GOOGLE_CLOUD_PROJECT") ||
    env.get("GCLOUD_PROJECT") ||
    env.get("gcloud_project") ||
    env.get("google_cloud_project")
  );
}

module.exports = {
  env,
  GOOGLE_CLOUD_PROJECT,
};
