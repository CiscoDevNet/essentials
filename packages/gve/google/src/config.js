const { Env } = require("@humanwhocodes/env");
const env = new Env();

/**
 * @see https://github.com/googleapis/google-auth-library-nodejs/blob/1ca3b733427d951ed624e1129fca510d84d5d0fe/src/auth/googleauth.ts#L646
 */
const GOOGLE_CLOUD_PROJECT = env.first([
  "GOOGLE_CLOUD_PROJECT",
  "GCLOUD_PROJECT",
  "gcloud_project",
  "google_cloud_project",
]);

module.exports = {
  env,
  GOOGLE_CLOUD_PROJECT,
};
