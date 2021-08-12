# Google

Utilities to work easily with [Google Cloud](https://cloud.google.com/).

## Installation

Install with [npm](https://www.npmjs.com/).

```bash
npm i @gve/google
```

## Usage

The `auth` module attempts to get Google application credentials from the [environment variable](https://cloud.google.com/docs/authentication/getting-started#setting_the_environment_variable) `GOOGLE_APPLICATION_CREDENTIALS`. If that fails, it looks for `GVE_GOOGLE_EMAIL` and `GVE_GOOGLE_KEY` to get them.

```js
const { auth: googleAuth } = require("@gve/google");
const dialogflow = require("@google-cloud/dialogflow");

const config = { credentials: googleAuth.credentials };
const sessionsClient = new dialogflow.SessionsClient(config);
```

## License

[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/)
