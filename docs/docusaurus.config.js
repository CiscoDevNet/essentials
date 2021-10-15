const lightCodeTheme = require("prism-react-renderer/themes/github");
const darkCodeTheme = require("prism-react-renderer/themes/dracula");

const lunrSearch = require.resolve("docusaurus-lunr-search");

// With JSDoc @type annotations, IDEs can provide config autocompletion
/** @type {import('@docusaurus/types').DocusaurusConfig} */
(
  module.exports = {
    title: "CiscoDevNet Essentials",
    tagline: "Packages to build, release, and run great software",
    url: "https://github.com",
    baseUrl: "/essentials/",
    onBrokenLinks: "warn",
    onBrokenMarkdownLinks: "throw",
    favicon: "img/favicon.ico",
    organizationName: "CiscoDevNet",
    projectName: "essentials",
    trailingSlash: true,

    plugins: [lunrSearch],

    presets: [
      [
        "@docusaurus/preset-classic",
        /** @type {import('@docusaurus/preset-classic').Options} */
        ({
          docs: {
            sidebarPath: require.resolve("./sidebars.js"),
            editUrl:
              "https://github.com/CiscoDevNet/essentials/edit/main/docs/",
          },
          blog: {
            showReadingTime: true,
            editUrl:
              "https://github.com/CiscoDevNet/essentials/edit/main/docs/",
          },
          theme: {
            customCss: require.resolve("./src/css/custom.css"),
          },
        }),
      ],
    ],

    themeConfig:
      /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
      ({
        navbar: {
          title: "CiscoDevNet Essentials",
          logo: {
            alt: "CiscoDevNet Essentials Logo",
            src: "img/logo.svg",
          },
          items: [
            {
              type: "doc",
              docId: "documentation",
              position: "left",
              label: "Documentation",
            },
            { to: "/blog", label: "Blog", position: "left" },
            {
              href: "https://github.com/CiscoDevNet/essentials",
              label: "GitHub",
              position: "right",
            },
          ],
        },
        footer: {
          style: "dark",
          links: [
            {
              title: "Community",
              items: [
                {
                  label: "Twitter",
                  href: "https://twitter.com/CiscoDevNet",
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
                  href: "https://github.com/CiscoDevNet/essentials",
                },
              ],
            },
          ],
          copyright: `Copyright ${new Date().getFullYear()} Cisco Systems, Inc. or its Affiliates`,
        },
        prism: {
          theme: lightCodeTheme,
          darkTheme: darkCodeTheme,
        },
      }),
  }
);
