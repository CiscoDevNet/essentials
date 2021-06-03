const debug = require("debug")("commands:gifs");

const axios = require("axios");
const fs = require("fs");
const FormData = require("form-data");
const { GiphyFetch } = require("@giphy/js-fetch-api");
const os = require("os");
const path = require("path");

// Utilities to save an image
const { promisify } = require("util");
const stream = require("stream");
const pipeline = promisify(stream.pipeline);
const mkdtemp = promisify(fs.mkdtemp);

const { BOT_ACCESS_TOKEN } = require("./config");
const {
  UNKNOWN,
  UNKNOWN_NUMBER,
  FAILURE,
} = require("@gve/analytics").PROPERTY_VALUES;

/**
 * Giphy search options
 *
 * @see https://developers.giphy.com/docs/api/endpoint/
 */
const searchOptions = {
  sort: "relevant",
  limit: 1,
  rating: "g",
};

const phrases = ["/gif", "gif"];

// Join the possible phrases into a regular expression.
const joiner = (joined, phrase) => `${joined}|^${phrase}`;
const phrase = RegExp(`^${phrases.reduce(joiner)}`);

/**
 * Custom event and properties for analytics.
 */
const eventTemplate = {
  name: "GIF Viewed",
  properties: {
    query_length: UNKNOWN_NUMBER,
    source: "https://giphy.com",
    status: FAILURE,
  },
};

class Gifs {
  constructor(apiKey) {
    this.apiKey = apiKey;
    this.fetch = new GiphyFetch(this.apiKey);

    this.getGif = this.getGif.bind(this);
    this.createDownloadsDir = this.createDownloadsDir.bind(this);

    this.downloads = "";
  }

  async createDownloadsDir(prefix = "tmp-gifs-") {
    const dirPath = path.join(os.tmpdir(), prefix);
    const dir = await mkdtemp(dirPath);
    console.log(`GIF directory created: ${dir}`);
    this.downloads = dir;
    return dir;
  }

  async updateController(controller) {
    this.controller = controller;
    const messageTypes = ["message", "direct_message"];
    this.controller.hears(phrase, messageTypes, this.getGif);

    await this.createDownloadsDir();

    return this.controller;
  }

  /**
   * Get a GIF using the message text to search.
   *
   * @see https://github.com/webex/webex-js-sdk/blob/master/packages/node_modules/@webex/internal-plugin-conversation/src/share-activity.js#L152-L234
   * @see https://github.com/webex/webex-js-sdk/blob/master/packages/node_modules/@webex/internal-plugin-conversation/src/share-activity.js#L100-L142
   * @param {*} bot
   * @param {*} message
   */
  async getGif(bot, message) {
    function random(max = 10) {
      return Math.floor(Math.random() * Math.floor(max));
    }

    const query = message.text.replace(phrase, "").trim();
    debug(`gif requested: ${query}`);

    // Update analytics event.
    const event = { ...eventTemplate };
    let { properties } = event;
    Object.assign(properties, { query_length: query.length });

    searchOptions.offset = random();
    const { data: gifs } = await this.fetch.search(query, searchOptions);

    if (gifs && gifs.length) {
      const gif = gifs[0];
      const { title, images } = gif;
      const { fixed_width: animated, fixed_width_still: still } = images;
      const { url } = animated;
      debug(`selected GIF: ${url}`);

      // Update analytics.
      Object.assign(properties, {
        gif_title: title || UNKNOWN,
        gif_url: url || UNKNOWN,
        gif_url_still: still.url || UNKNOWN,
      });

      const filePath = path.join(this.downloads, `${query}.gif`);
      const fileWriterStream = fs.createWriteStream(filePath);

      const response = await axios({
        method: "get",
        url,
        responseType: "stream",
      });
      const { data: downloadStream } = response;

      try {
        await pipeline(downloadStream, fileWriterStream);
        console.log(`GIF downloaded to ${filePath}`);

        const fileReaderStream = fs.createReadStream(filePath, {
          displayName: title,
          filetype: "image/gif",
          fileType: "image/gif",
          mimeType: "image/gif",
          type: "image/gif",
          objectType: "file",
          url: "https://giphy.com",
          image: {
            url: "https://giphy.com",
          },
        });

        const form = new FormData();
        const { roomId } = message;
        form.append("roomId", roomId);
        form.append("files", fileReaderStream, `${query}.gif`);

        // Update analytics.
        Object.assign(properties, { space_id: roomId });

        // Set boundary in the header field 'Content-Type'.
        const formHeaders = form.getHeaders();

        await axios.post("https://api.ciscospark.com/v1/messages", form, {
          headers: {
            ...formHeaders,
            Authorization: `Bearer ${BOT_ACCESS_TOKEN}`,
          },
        });
        debug(`uploaded ${filePath}`);
      } catch (error) {
        console.error(error);
        await this.notifyFailure(bot, message, event);
      }
    } else {
      await this.notifyFailure(bot, message, event);
    }
  }

  async notifyFailure(bot, message, event) {
    const text = "I'm sorry, I couldn't find a suitable GIF. 😔";
    const reply = {
      text,
      markdown: text,
      event,
    };
    await bot.reply(message, reply);
  }
}

module.exports = Gifs;
