const { Env } = require("@humanwhocodes/env");
const env = new Env();

const GVE_GOOGLE_PROJECT_ID = env.get("GVE_GOOGLE_PROJECT_ID");

module.exports = {
  env,
  GVE_GOOGLE_PROJECT_ID,
};
