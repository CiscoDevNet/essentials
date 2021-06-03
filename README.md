# Essentials

Essential packages to build, release, and run great software.

- Create intelligent bots with [Adaptive Cards](https://adaptivecards.io/)
- Gather and send analytics
- Deploy Docker containers to [Google Cloud](https://cloud.google.com/) or [OpenShift](https://www.openshift.com/)

[![lerna](https://img.shields.io/badge/maintained%20with-lerna-cc00ff.svg)](https://lerna.js.org/)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-1.4-4baaaa.svg)](code_of_conduct.md)

## Example

```js
// Create a Webex bot with Botkit.

const { Botkit } = require("botkit");
const { WebexAdapter } = require("botbuilder-adapter-webex");

const adapter = new WebexAdapter({
  access_token: "<BOT_ACCESS_TOKEN>",
  public_address: "<BOT_URL>",
  secret: "<BOT_SECRET>",
});

const controller = new Botkit({
  adapter,
  webhook_uri: "/api/messages",
});

// Use the product analytics middleware. 👇

const { Analytics } = require("@gve/bot-middleware");

const analyticsMiddleware = new Analytics("<ANALYTICS_API_KEY>");
controller.middleware.receive.use(analyticsMiddleware.trackUserMessage);
controller.middleware.send.use(analyticsMiddleware.trackBotMessage);
```

Now basic properties from all messages are automatically ✨ sent to analytics, including:

- message ID
- message time
- sender's domain, e.g., cisco.com
- if the conversation is one-on-one or in a group
- more!

## Installation

Clone this repository.

Install its dependencies with [npm](https://www.npmjs.com/).

```bash
cd essentials
npm ci
```

Bootstrap the project with [Lerna](https://github.com/lerna/lerna).

```bash
npx lerna bootstrap
```

## License

[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/)
