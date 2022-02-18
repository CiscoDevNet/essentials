const Command = require("./index");
const EventEmitter = require("events");

describe("Command", () => {
  it("can emit events", () => {
    const command = new Command();
    expect(command).toBeInstanceOf(EventEmitter);
  });
});
