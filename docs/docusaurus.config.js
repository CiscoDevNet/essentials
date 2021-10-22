const { Env } = require("@humanwhocodes/env");
const debug = require("debug")("docs");
const lunrSearch = require.resolve("docusaurus-lunr-search");

const lightCodeTheme = require("prism-react-renderer/themes/github");
const darkCodeTheme = require("prism-react-renderer/themes/dracula");

const env = new Env();
const plugins = [lunrSearch];

// Get the current branch.
const branch = env.get("GIT_BRANCH", "main");

// Configure the analytics tracking ID.
const trackingID = env.get("GOOGLE_ANALYTICS_TRACKING_ID");
let gtag;
if (trackingID) {
  gtag = { trackingID };
  debug(`Tracking enabled. Sending analytics to ${trackingID}`);
} else {
  debug("Tracking disabled.");
}

// With JSDoc @type annotations, IDEs can provide config autocompletion
/** @type {import('@docusaurus/types').DocusaurusConfig} */
(
  module.exports = {
    title: "Cisco DevNet Essentials",
    tagline: "Make great software. Run it in the Cloud.",
    url: "https://github.com",
    baseUrl: "/essentials/",
    onBrokenLinks: "warn",
    onBrokenMarkdownLinks: "throw",
    favicon: "img/favicon.ico",
    organizationName: "CiscoDevNet",
    projectName: "essentials",
    trailingSlash: true,

    plugins,

    presets: [
      [
        "@docusaurus/preset-classic",
        /** @type {import('@docusaurus/preset-classic').Options} */
        ({
          docs: {
            sidebarPath: require.resolve("./sidebars.js"),
            editUrl: `https://github.com/CiscoDevNet/essentials/edit/${branch}/docs/`,
          },
          blog: {
            showReadingTime: true,
            editUrl: `https://github.com/CiscoDevNet/essentials/edit/${branch}/docs/`,
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
        colorMode: {
          switchConfig: {
            darkIcon: "🌙",
            lightIcon: "☀️",
          },
        },
        navbar: {
          title: "DevNet Essentials",
          logo: {
            alt: "DevNet Essentials Logo",
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
        gtag,
        prism: {
          theme: lightCodeTheme,
          darkTheme: darkCodeTheme,
        },
      }),
  }
);
