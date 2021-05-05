class RollbackError extends Error {
  constructor(original = "original file", backup = "backup file") {
    super();
    this.message = `Could not rollback to ${original}. Please use ${backup} to manually restore the file.`;
  }
}

module.exports = RollbackError;
