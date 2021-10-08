const { normalizeUrl } = require("./index");

describe("normalizeUrl", () => {
  it("normalizes a URL", () => {
    const url =
      "http://www.cisco.com/c/en/us/products/datasheet-c78-741988.html";
    let normalizedUrl = normalizeUrl(url);
    expect(normalizedUrl).toEqual(
      "http://www.cisco.com/c/en/us/products/datasheet-c78-741988.html"
    );
  });
  it("normalizes a secure URL", () => {
    const secureUrl =
      "https://www.cisco.com/c/en/us/products/datasheet-c78-741988.html";
    normalizedUrl = normalizeUrl(secureUrl);
    expect(normalizedUrl).toEqual(
      "https://www.cisco.com/c/en/us/products/datasheet-c78-741988.html"
    );
  });
  it("normalizes a malformed URL", () => {
    const url = "://www.cisco.com/c/en/us/products/datasheet-c78-741988.html";
    const normalizedUrl = normalizeUrl(url);
    expect(normalizedUrl).toEqual(
      "http://www.cisco.com/c/en/us/products/datasheet-c78-741988.html"
    );
  });
});
