const { Env } = require("@humanwhocodes/env");
const env = new Env();

const GOOGLE_APPLICATION_CREDENTIALS = env.get(
  "GOOGLE_APPLICATION_CREDENTIALS"
);
const GOOGLE_PROJECT_ID = env.get("GOOGLE_PROJECT_ID");
const GOOGLE_EMAIL = env.get("GOOGLE_EMAIL");
const GOOGLE_KEY = env.get("GOOGLE_KEY");

module.exports = {
  env,
  GOOGLE_APPLICATION_CREDENTIALS,
  GOOGLE_EMAIL,
  GOOGLE_KEY,
  GOOGLE_PROJECT_ID,
};
