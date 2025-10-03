# Analytics

Analytics events and constants to track system usage.

## Installation

Install with [npm](https://www.npmjs.com/).

```bash
npm i @cisco/analtyics
```

## Usage

```js
const { AnalyticsEvent, EVENTS } = require("@cisco/analytics");

const analyticsEvent = new AnalyticsEvent(EVENTS.MESSAGE_SENT);
```

## License

[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/)
