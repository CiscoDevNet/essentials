class HttpError extends Error {
  constructor(message, response) {
    super(message);
    this.response = response;
  }
}

module.exports = HttpError;
