class DirectoryError extends Error {
  constructor(directory) {
    super();
    this.message = `${directory} is not a directory`;
  }
}

module.exports = DirectoryError;
