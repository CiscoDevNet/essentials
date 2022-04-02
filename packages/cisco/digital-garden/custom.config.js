const lightCodeTheme = require("prism-react-renderer/themes/github");
const darkCodeTheme = require("prism-react-renderer/themes/dracula");
const { docusaurus } = require("./config");

const { basicConfig, title, repoPath, repoTreePath } = docusaurus;

const DOCS_ENABLED = {
  sidebarPath: require.resolve("./sidebars.js"),
  editUrl: repoTreePath,
};

const BLOG_ENABLED = {
  showReadingTime: true,
  editUrl: repoTreePath,
};

const docs = DOCS_ENABLED;
// const docs = false;

const blog = BLOG_ENABLED;
// const blog = false;

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
        { to: "/blog", label: "Blog", position: "left" },
        {
          href: repoPath,
          label: "GitHub",
          position: "right",
        },
      ],
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
            {
              label: "Blog",
              to: "/blog",
            },
            {
              label: "GitHub",
              href: repoPath,
            },
          ],
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
