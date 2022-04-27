const Image = require("./image");

describe("Image", () => {
  it("creates a container image", () => {
    const image = new Image();
    expect(image).toBeTruthy();
  });
});
