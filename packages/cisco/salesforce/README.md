# Salesforce

Query and update [Salesforce](https://www.salesforce.com/) with built-in retries.

## Installation

Install with [npm](https://www.npmjs.com/).

```bash
npm i @gve/salesforce
```

## Usage

```js
const { Salesforce, DirectAdapter } = require("@gve/salesforce");

const adapter = new DirectAdapter("<USERNAME>", "<PASSWORD>", "<URL>");
const salesforce = new Salesforce(SALESFORCE_URL, adapter);

salesforce
  .login()
  .then(() => {
    console.info("Salesforce connected");
  })
  .then(() => {
    const users = await salesforce.users.get("<Salesforce User ID>");
    console.log(users);
  })
  .catch((error) => {
    console.error("Salesforce not connected");
    debug(error.message);
  });
```

## License

[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/)
