const { Salesforce, adapters, errors } = require("./index");
const { DirectAdapter } = adapters;

const Accounts = jest.mock("./adapters/direct/accounts");

it("imports Salesforce", () => {
  expect(Salesforce).toBeDefined();
});

it("imports Salesforce adapters", () => {
  expect(DirectAdapter).toBeDefined();
});

it("imports Salesforce errors", () => {
  expect(errors).toBeDefined();
  expect(Object.keys(errors).length).toBe(4);
});

xdescribe("constructor", () => {
  beforeEach(() => {
    Accounts.mockClear();
  });

  it("creates object with direct adapter", () => {
    const url = "salesforce.com";
    const adapterOptions = { Accounts: new Accounts() };
    const adapter = new DirectAdapter(
      "username",
      "password",
      url,
      adapterOptions
    );
    const salesforce = new Salesforce("salesforce.com", adapter);
    expect(salesforce).toBeTruthy();
  });
});
