# Bot commands

Create responsive bot commands with ease.

## Installation

Install with [npm](https://www.npmjs.com/).

```bash
npm i @gve/bot-commands
```

## Usage

```js
const { Command } = require("@gve/bot-commands");

const phrases = ["hello", "hi", "hey"];

class Hello extends Command {
  constructor(intent = "hello", config = { phrases }) {
    super(intent, config);
    this.handleText = this.sayHello.bind(this);
  }

  async sayHello(bot, message) {
    await bot.say("Hello 👋");
  }
}
```

## License

[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/)
