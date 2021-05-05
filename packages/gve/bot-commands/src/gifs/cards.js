const { Card } = require("@gve/cards");

class GifCard extends Card {
  constructor(url, title) {
    super();

    this.body = [
      {
        type: "Image",
        url,
        altText: title,
      },
    ];

    this.placeholderText = title;
  }
}

module.exports = { GifCard };
