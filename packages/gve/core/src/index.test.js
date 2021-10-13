const { getDomain, normalizeUrl } = require("./index");

const URL = "http://www.cisco.com/c/en/us/products/datasheet-c78-741988.html";
const SECURE_URL =
  "https://www.cisco.com/c/en/us/products/datasheet-c78-741988.html";
const MALFORMED_URL =
  "://www.cisco.com/c/en/us/products/datasheet-c78-741988.html";

describe("normalizeUrl", () => {
  it("normalizes a URL", () => {
    const normalizedUrl = normalizeUrl(URL);
    expect(normalizedUrl).toEqual(
      "http://www.cisco.com/c/en/us/products/datasheet-c78-741988.html"
    );
  });
  it("normalizes a secure URL", () => {
    const normalizedUrl = normalizeUrl(SECURE_URL);
    expect(normalizedUrl).toEqual(
      "https://www.cisco.com/c/en/us/products/datasheet-c78-741988.html"
    );
  });
  it("normalizes a malformed URL", () => {
    const normalizedUrl = normalizeUrl(MALFORMED_URL);
    expect(normalizedUrl).toEqual(
      "http://www.cisco.com/c/en/us/products/datasheet-c78-741988.html"
    );
  });
});

describe("getDomain", () => {
  it("extracts the domain from a URL", () => {
    const domain = getDomain(URL);
    expect(domain).toEqual("cisco.com");
  });
  it("extracts the domain from a secure URL", () => {
    const domain = getDomain(SECURE_URL);
    expect(domain).toEqual("cisco.com");
  });
  it("extracts the domain from a malformed URL", () => {
    const domain = getDomain(MALFORMED_URL);
    expect(domain).toEqual("cisco.com");
  });
});
