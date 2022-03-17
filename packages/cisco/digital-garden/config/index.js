const path = require("path");

// Load environment variables from file.
const dotenv = require("dotenv");
dotenv.config();

const { Env } = require("@humanwhocodes/env");
const env = new Env();

// Required

// GitHub org or user name
const organizationName = env.require("CONFIG_SITE_REPO_ORG_NAME");
// GitHub repo name
const projectName = env.require("CONFIG_SITE_REPO_PROJECT_NAME");
const url = env.require("CONFIG_SITE_URL");

// Defaults provided

const title = env.get("CONFIG_SITE_TITLE", "My Site");
const tagline = env.get("CONFIG_SITE_TAGLINE", "");

/** @type {import('@docusaurus/types').Config} */
const basicConfig = {
  title,
  tagline,
  url,
  baseUrl: "/",
  onBrokenLinks: "throw",
  onBrokenMarkdownLinks: "throw",
  favicon: "img/favicon.ico",
  organizationName,
  projectName,
};

const repoBaseUrl = env.get("CONFIG_SITE_REPO_BASE_URL", "https://github.com");
const repoPath = path.join("/", organizationName, projectName);
const repoUrl = new URL(repoPath, repoBaseUrl).toString();

module.exports = { env, basicConfig, repoUrl };
