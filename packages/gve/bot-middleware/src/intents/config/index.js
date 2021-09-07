const { env } = require("../../config");

const INTENT_CONFIDENCE = env.get("INTENT_CONFIDENCE", 0.5);

module.exports = {
  INTENT_CONFIDENCE,
};
