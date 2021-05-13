const { env } = require("../config");

const { CREDENTIALS } = require("./google/config");
const INTENT_CONFIDENCE = env.get("INTENT_CONFIDENCE", 0.5);

module.exports = {
  CREDENTIALS,
  INTENT_CONFIDENCE,
};
