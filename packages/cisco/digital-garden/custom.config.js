const lightCodeTheme = require("prism-react-renderer/themes/github");
const darkCodeTheme = require("prism-react-renderer/themes/dracula");
const { blog: blogConfig, docusaurus } = require("./config");

const { basicConfig, title, repoPath, repoTreePath } = docusaurus;

const DOCS_ENABLED = {
  sidebarPath: require.resolve("./sidebars.js"),
  editUrl: repoTreePath,
};

const docs = DOCS_ENABLED;
// const docs = false;

const BLOG_ITEM = {
  label: "Blog",
  to: "/blog",
};

let blog = false;
let blogNavBarItem;
let blogFooterItem;

if (blogConfig.isEnabled) {
  blog = {
    showReadingTime: true,
    editUrl: repoTreePath,
  };

  blogNavBarItem = { ...BLOG_ITEM, position: "left" };
  blogFooterItem = { ...BLOG_ITEM };
}

basicConfig.presets = [
  [
    "classic",
    /** @type {import('@docusaurus/preset-classic').Options} */
    ({
      docs,
      blog,
      theme: {
        customCss: require.resolve("./src/css/custom.css"),
      },
    }),
  ],
];

basicConfig.themeConfig =
  /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
  {
    navbar: {
      title,
      logo: {
        alt: `${title} Logo`,
        src: "img/logo.svg",
      },
      items: [
        {
          type: "doc",
          docId: "intro",
          position: "left",
          label: "Tutorial",
        },
        blogNavBarItem,
        {
          href: repoPath,
          label: "GitHub",
          position: "right",
        },
      ].filter(Boolean),
    },
    footer: {
      style: "dark",
      links: [
        {
          title: "Docs",
          items: [
            {
              label: "Tutorial",
              to: "/docs/intro",
            },
          ],
        },
        {
          title: "Community",
          items: [
            {
              label: "Stack Overflow",
              href: "https://stackoverflow.com/questions/tagged/cisco+javascript",
            },
            {
              label: "Twitter",
              href: "https://twitter.com/ciscodevnet",
            },
          ],
        },
        {
          title: "More",
          items: [
            blogFooterItem,
            {
              label: "GitHub",
              href: repoPath,
            },
          ].filter(Boolean),
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} My Project, Inc. Built with Docusaurus.`,
    },
    prism: {
      theme: lightCodeTheme,
      darkTheme: darkCodeTheme,
    },
  };

module.exports = basicConfig;
