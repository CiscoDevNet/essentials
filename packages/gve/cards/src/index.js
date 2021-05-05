/**
 * @file Adaptive Card
 */

const moment = require("moment");

const contentType = "application/vnd.microsoft.card.adaptive";
const { icon } = require("./constants");

/**
 * Adaptive Card
 *
 * Adaptive Card based on the {@link https://adaptivecards.io/explorer/ Adaptive Card schema}.
 * @typedef {Object} AdaptiveCard
 */
class Card {
  constructor() {
    // Additional props needed by original structure
    this.contentType = contentType;
    this.$schema = "http://adaptivecards.io/schemas/adaptive-card.json";

    // New structure from
    // https://docs.microsoft.com/en-us/adaptive-cards/sdk/rendering-cards/javascript/render-a-card#render-a-card
    this.type = "AdaptiveCard";
    this.version = "1.0";

    this.body = [];
    this.actions = [];
  }

  static formatDate(date) {
    return moment(date).format("YYYY-MM-DDTHH:mm:ss[Z]");
  }
}
class CardMessage {
  constructor(card, placeholderText, event) {
    this.attachments = [
      {
        content: card,
        contentType,
      },
    ];
    this.text = placeholderText;
    this.event = event;
  }
}

class Header {
  constructor(text, weight = "bolder", size = "medium") {
    this.type = "TextBlock";
    this.text = text;
    this.weight = weight;
    this.size = size;
  }
}

class IconHeader {
  constructor(image, text) {
    this.type = "ColumnSet";
    this.columns = [
      {
        type: "Column",
        width: "auto",
        items: [
          {
            type: "Image",
            url: image,
            size: "small",
          },
        ],
      },
      {
        type: "Column",
        width: "stretch",
        items: [{ ...new Header(text), wrap: true }],
      },
    ];
  }
}

/**
 * Text input.
 * @see https://shoelace.style/components/form
 */
class Input {
  constructor(
    name,
    label = name,
    placeholder = "",
    value = "",
    isRequired = false
  ) {
    this.type = "Container";
    this.items = [
      {
        type: "TextBlock",
        text: label,
      },
      {
        type: "Input.Text",
        id: name,
        placeholder,
        isRequired,
        value,
      },
    ];
  }
}

class Property {
  constructor(key, value) {
    this.title = key;
    this.value = value || "Unknown";
  }
}

class Choices {
  constructor(id, items, selected) {
    this.type = "Input.ChoiceSet";
    this.value = selected || "";
    this.id = id;
    this.isMultiSelect = false;
  }

  /**
   * @typedef Choice
   * @param {String} choice - title of the choice as it appears in the UI
   * @param {String} value - value of the choice "behind-the-scenes"
   */

  /**
   * Constructs a Choice.
   *
   * The optional delimiter is helpful for choices that contain commas.
   * Commas are used by Adaptive Cards by default to denote multiple choices selected.
   * The delimiter allows such strings to be parsed later.
   *
   * @param {Object|String} choice - choice
   * @param {String} delim - delimiter separating choices of a multiselect field
   */
  getChoice(choice, delim = "") {
    const title =
      choice.label || choice.title || choice.text || choice.toString();
    const value = choice.value || choice.id || title;
    return {
      title,
      value: `${value}${delim}`,
    };
  }
}

class Dropdown extends Choices {
  constructor(id, items, selected) {
    super(id, items, selected);
    this.style = "compact";
    this.choices = items.map((item) => this.getChoice(item));
  }
}

class Radio extends Choices {
  constructor(id, items, selected) {
    super(id, items, selected);
    this.style = "expanded";
    this.choices = items.map((item) => this.getChoice(item));
  }
}

class Checkbox extends Choices {
  constructor(id, items, selected) {
    super(id, items, selected);
    this.style = "expanded";
    this.isMultiSelect = true;
    this.choices = items.map((item) => this.getChoice(item, ";"));
  }
}

class SearchResult {
  constructor(title, url, content, favicon) {
    this.type = "Container";
    this.items = this.getItems(title, url, content, favicon);
  }

  getItems(title, url, content, favicon) {
    // Title
    const titleElement = {
      type: "TextBlock",
      text: `[${title}](${url})`,
      size: "medium",
      wrap: false,
    };

    const items = [titleElement];

    // Link
    if (url) {
      const link = {
        type: "Container",
        items: this.getLinkItems(url, favicon),
      };
      items.push(link);
    }

    // Content
    const contentElement = {
      type: "TextBlock",
      text: content,
      wrap: true,
    };
    items.push(contentElement);

    return items;
  }

  getLinkItems(url, favicon) {
    const container = {
      type: "ColumnSet",
      columns: this.getColumns(url, favicon),
      selectAction: {
        type: "Action.OpenUrl",
        url,
      },
    };

    return [container];
  }

  getColumns(url, favicon) {
    const image = {
      type: "Image",
      url: favicon || icon.default,
      height: icon.height,
      horizontalAlignment: "Center",
      verticalContentAlignment: "Center",
    };
    const link = {
      type: "TextBlock",
      text: `${url}`,
      color: "light",
      wrap: false,
    };
    return [
      { type: "Column", width: icon.width, items: [image] },
      { type: "Column", width: "stretch", items: [link] },
    ];
  }
}

module.exports = {
  Card,
  CardMessage,
  Checkbox,
  Header,
  IconHeader,
  Input,
  Property,
  Dropdown,
  Radio,
  SearchResult,
};
