const { Salesforce } = require("./index");

const {
  SALESFORCE_CONNECTION_USERNAME,
  SALESFORCE_CONNECTION_PASSWORD,
} = process.env;
const { SALESFORCE_CONNECTION_URL } = require("./config");

xtest("creates default Salesforce object", () => {
  const salesforce = new Salesforce();
  const { username, password, url, user, connection, connected } = salesforce;

  expect(username).toBeUndefined();
  expect(password).toBeUndefined();
  expect(url).toBe(SALESFORCE_CONNECTION_URL);

  expect(user).toBeDefined();
  expect(user.username).toBe(username);

  expect(connection).toBeDefined();
  expect(connected).toBe(false);
});

xtest("overrides default URL", () => {
  const url = "https://www.example.com";
  const salesforce = new Salesforce(undefined, undefined, url);
  expect(salesforce.url).toBe(url);
});

xdescribe("creates Salesforce object", () => {
  let salesforce;
  let user;

  beforeAll(async () => {
    salesforce = new Salesforce(
      SALESFORCE_CONNECTION_USERNAME,
      SALESFORCE_CONNECTION_PASSWORD
    );
    user = await salesforce.login();

    const { username, id, organizationId, url, accessToken } = user;
    expect(username).toBe(salesforce.username);
    expect(id).toBeDefined();
    expect(organizationId).toBeDefined();
    expect(url).toBeDefined();
    expect(accessToken).toBeDefined();
    expect(salesforce.connected).toBe(true);
  });

  test("does not login if user is already logged in", async () => {
    const mockLogin = jest.fn();
    salesforce.connection.login = mockLogin;

    user = await salesforce.login();
    expect(mockLogin.mock.calls.length).toBe(0);
    expect(salesforce.connected).toBe(true);
  });

  describe("Cases", () => {
    const { cases } = require("./constants");

    test("constructs cases object", () => {
      const {
        create,
        get,
        update,
        org,
        origin,
        owner,
        recordType,
      } = salesforce.cases;

      expect(typeof create).toEqual("function");
      expect(typeof get).toEqual("function");
      expect(typeof update).toEqual("function");

      expect(org).toEqual(cases.org);
      expect(origin).toEqual(cases.origin);
      expect(owner.alias).toEqual(cases.owner.alias);
      expect(owner.name).toEqual(cases.owner.name);
      expect(recordType.id).toEqual(cases.recordType.id);
      expect(recordType.name).toEqual(cases.recordType.name);
    });

    xtest("describes Case object", async () => {
      const myCase = await salesforce.cases.describe();
      console(myCase);
      expect(myCase).toBeDefined();
    });
  });

  describe("Users", () => {
    test("constructs users object", () => {
      const { get } = salesforce.users;
      expect(typeof get).toEqual("function");
    });
  });

  xdescribe("Opportunities", () => {
    test("describes Opportunity object", async () => {
      const opportunity = await salesforce.opportunities.get();
      console.log(opportunity);
    });
    describe("gets Opportunity", () => {
      test("by Opportunity ID", async () => {
        const opportunityId = "0062T00001EyxMJ";
        let opportunity;
        try {
          opportunity = await salesforce.opportunities.get({
            id: opportunityId,
          });
          expect(opportunity).toBeDefined();
        } catch (error) {
          console.log(error);
          console.log(opportunity);
        }
      });

      test("by Deal ID", async () => {
        const dealId = "20071661";
        const opportunity = await salesforce.opportunities.get({
          DealId: dealId,
        });

        expect(opportunity).toBeDefined();
      });
    });
  });
});
