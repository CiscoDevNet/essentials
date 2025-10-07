class ServiceUnreachableError extends Error {
  constructor(message) {
    super(message);
  }
}

module.exports = ServiceUnreachableError;
