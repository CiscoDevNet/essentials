const { env, GVE_GOOGLE_PROJECT_ID } = require("../config");

const GOOGLE_APPLICATION_CREDENTIALS = env.get(
  "GOOGLE_APPLICATION_CREDENTIALS"
);

let GVE_GOOGLE_EMAIL;
let GVE_GOOGLE_KEY;

getCredentials();

function getCredentials() {
  if (!GOOGLE_APPLICATION_CREDENTIALS) {
    GVE_GOOGLE_EMAIL = env.require("GVE_GOOGLE_EMAIL");
    GVE_GOOGLE_KEY = env.require("GVE_GOOGLE_KEY");
  }
}

module.exports = {
  env,
  GOOGLE_APPLICATION_CREDENTIALS,
  GVE_GOOGLE_EMAIL,
  GVE_GOOGLE_KEY,
  GVE_GOOGLE_PROJECT_ID,
};
