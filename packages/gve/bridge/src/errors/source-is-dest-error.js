class SourceIsDestError extends Error {
  constructor() {
    super();
    this.message = "source directory is same as destination directory";
  }
}

module.exports = SourceIsDestError;
