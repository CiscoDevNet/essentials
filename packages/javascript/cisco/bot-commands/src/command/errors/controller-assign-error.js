class ControllerAssignError extends Error {
  constructor() {
    super("Cannot assign controller to the command");
  }
}

module.exports = ControllerAssignError;
