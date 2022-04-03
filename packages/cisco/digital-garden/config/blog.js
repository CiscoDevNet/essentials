const env = require("./env");
const { default: forceBoolean } = require("force-boolean");

const isEnabled = forceBoolean(env.get("CONFIG_SITE_BLOG_IS_ENABLED", true));

module.exports = { isEnabled };
