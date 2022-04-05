# Cards

Create [Adaptive Cards](https://adaptivecards.io/), components, and rich messages for bot platforms and more - without having to remember the [boilerplate](https://docs.microsoft.com/en-us/adaptive-cards/authoring-cards/getting-started#example-card).

## Installation

Install with [npm](https://www.npmjs.com/).

```bash
npm i @gve/cards
```

## Usage

```js
const { Card, Header, Property } = require("@gve/cards");

class RookieCard extends Card {
  constructor(playerName, team, position) {
    super();
    this.body = [
      type: "Container",
      items: [
        new Header(`${playerName}'s Rookie Card`),
        {
          type: "FactSet",
          facts: [
            new Property("Player", playerName),
            new Property("Team", team),
            new Property("Position", position),
          ]
        },
      ]
    ];
  }
}
```

## License

[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/)
