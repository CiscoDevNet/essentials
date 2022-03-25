const path = require("path");

// Required by Docusaurus.
const DEFAULT_SITE_TITLE = "My Site";
const DEFAULT_SITE_BASE_PATH = "/";

// Not required, but good to have.
const DEFAULT_SITE_ON_BROKEN_LINKS = "throw";
const DEFAULT_SITE_ON_BROKEN_MARKDOWN_LINKS = "warn";
const DEFAULT_SITE_FAVICON_PATH = "img/favicon.ico";

const DEFAULT_STANDARD_CONFIG = {
  title: DEFAULT_SITE_TITLE,
  baseUrl: DEFAULT_SITE_BASE_PATH,
  onBrokenLinks: DEFAULT_SITE_ON_BROKEN_LINKS,
  onBrokenMarkdownLinks: DEFAULT_SITE_ON_BROKEN_MARKDOWN_LINKS,
  favicon: DEFAULT_SITE_FAVICON_PATH,
};

// Optional.
const DEFAULT_REPO_BRANCH = "main";
const DEFAULT_REPO_URL_BASE = "https://github.com";
const DEFAULT_REPO_DIR_PATH = "";

const DEFAULT_CUSTOM_CONFIG = {
  repoBranch: DEFAULT_REPO_BRANCH,
  repoBaseUrl: DEFAULT_REPO_URL_BASE,
};

const DEFAULT_CONFIG = { ...DEFAULT_STANDARD_CONFIG, ...DEFAULT_CUSTOM_CONFIG };

class Docusaurus {
  constructor(organizationName, projectName, url, config = DEFAULT_CONFIG) {
    this.organizationName = organizationName;
    this.projectName = projectName;
    this.url = url;

    let baseUrl,
      title,
      favicon,
      onBrokenLinks,
      onBrokenMarkdownLinks,
      tagline,
      repoBranch,
      repoDirPath,
      repoUrlBase;

    ({
      title = DEFAULT_SITE_TITLE,
      baseUrl = DEFAULT_SITE_BASE_PATH,
      favicon = DEFAULT_SITE_FAVICON_PATH,
      onBrokenLinks = DEFAULT_SITE_ON_BROKEN_LINKS,
      onBrokenMarkdownLinks = DEFAULT_SITE_ON_BROKEN_MARKDOWN_LINKS,
      tagline,
      repoBranch = DEFAULT_REPO_BRANCH,
      repoDirPath,
      repoUrlBase = DEFAULT_REPO_URL_BASE,
    } = config);

    // Docusaurus props
    this.title = title;
    this.baseUrl = baseUrl;
    this.favicon = favicon;
    this.onBrokenLinks = onBrokenLinks;
    this.onBrokenMarkdownLinks = onBrokenMarkdownLinks;
    this.tagline = tagline;

    // Custom props
    this.repoUrlBase = repoUrlBase;
    this.repoBranch = repoBranch;
    this.repoDirPath = repoDirPath;
  }

  get basicConfig() {
    const {
      title,
      baseUrl,
      favicon,
      onBrokenLinks,
      onBrokenMarkdownLinks,
      tagline,
      url,
    } = this;

    /** @type {import('@docusaurus/types').Config} */
    return {
      title,
      baseUrl,
      favicon,
      onBrokenLinks,
      onBrokenMarkdownLinks,
      tagline,
      url,
      organizationName: this.organizationName,
      projectName: this.projectName,
    };
  }

  get customFields() {
    const { repoUrlBase, repoBranch, repoDirPath } = this;
    return {
      repoUrlBase,
      repoBranch,
      repoDirPath,
    };
  }

  get repoEditPath() {
    return this._getExpandedRepoPath("edit");
  }

  get repoTreePath() {
    return this._getExpandedRepoPath();
  }

  _getExpandedRepoPath(partialPath = "tree") {
    const expandedPath = this._getExpandedPath(partialPath);
    return new URL(`/${expandedPath}`, this.repoPath).toString();
  }

  _getExpandedPath(partialPath) {
    return path.join(
      this._repoPartialPath,
      partialPath,
      this.repoBranch,
      this.repoDirPath || DEFAULT_REPO_DIR_PATH
    );
  }

  get repoPath() {
    return new URL(`/${this._repoPartialPath}`, this.repoUrlBase).toString();
  }

  /**
   * private
   */
  get _repoPartialPath() {
    return path.join(this.organizationName, this.projectName);
  }
}

module.exports = Docusaurus;
