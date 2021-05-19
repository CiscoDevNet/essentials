/**
 * The default analytics URL
 * @constant {String}
 */
const DEFAULT_ANALYTICS_URL = "https://api.amplitude.com/2/httpapi";

module.exports = {
  ANALYTICS_API_KEY: process.env.ANALYTICS_API_KEY,
  ANALYTICS_URL: process.env.ANALYTICS_URL || DEFAULT_ANALYTICS_URL,
};
