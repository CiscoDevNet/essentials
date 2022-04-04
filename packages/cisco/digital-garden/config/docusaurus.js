const { Docusaurus } = require("@cisco/docs-docusaurus");
const env = require("./env");

const organizationName = env.require("CONFIG_SITE_REPO_ORG_NAME");
const projectName = env.require("CONFIG_SITE_REPO_PROJECT_NAME");
const url = env.require("CONFIG_SITE_URL");

const title = env.get("CONFIG_SITE_TITLE", "My Site");
const tagline = env.get("CONFIG_SITE_TAGLINE", "");

const repoBranch = env.get("CONFIG_SITE_REPO_BRANCH");
const repoDirPath = env.get("CONFIG_SITE_REPO_DIR_PATH");

const additionalConfig = { title, tagline, repoBranch, repoDirPath };

let docusaurus = new Docusaurus(
  organizationName,
  projectName,
  url,
  additionalConfig
);

module.exports = docusaurus;
