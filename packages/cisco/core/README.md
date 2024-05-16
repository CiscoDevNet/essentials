# Core

Use helpful functions to reduce parsing and errors.

## Installation

Install with [npm](https://www.npmjs.com/).

```bash
npm i @cisco/core
```

## Usage

```js
const { getDomain } = require("@cisco/core");

const malformedUrl = "://www.cisco.com/c/en/us/products/datasheet.html";
const domain = getDomain(malformedUrl);
console.log(domain);
```

Prints `cisco.com`.

## License

[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/)
