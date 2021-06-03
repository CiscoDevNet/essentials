# Bot middleware

Middleware to intercept messages. For example, gather and send analytics.

## Installation

Install with [npm](https://www.npmjs.com/).

```bash
npm i @gve/bot-middleware
```

## Usage

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

## License

[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/)
