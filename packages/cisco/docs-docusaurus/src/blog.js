const BLOG_ITEM = {
  label: "Blog",
  to: "/blog",
};

const DEFAULT_STANDARD_CONFIG = {
  showReadingTime: true,
};

const DEFAULT_CUSTOM_CONFIG = {
  isEnabled: true,
};

const DEFAULT_CONFIG = { ...DEFAULT_STANDARD_CONFIG, ...DEFAULT_CUSTOM_CONFIG };

class Blog {
  constructor(editUrl, config = DEFAULT_CONFIG) {
    this.editUrl = editUrl;
    let isEnabled, showReadingTime;

    ({
      isEnabled = DEFAULT_CUSTOM_CONFIG.isEnabled,
      showReadingTime = DEFAULT_STANDARD_CONFIG.showReadingTime,
    } = config);

    this.isEnabled = isEnabled;
    this.showReadingTime = showReadingTime;
  }

  get navBarItem() {
    return this.isEnabled ? { ...BLOG_ITEM, position: "left" } : undefined;
  }

  get footerItem() {
    return this.isEnabled ? { ...BLOG_ITEM } : undefined;
  }
}

module.exports = Blog;
