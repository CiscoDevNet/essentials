const Image = require("./image");

describe("Image", () => {
  it("creates a container image", () => {
    const image = new Image();
    expect(image).toBeTruthy();
  });

  describe("gets the file flags", () => {
    it("with no given compose files", () => {
      const image = new Image();
      const fileFlags = image._getFileFlags();
      expect(fileFlags.length).toEqual(0);
    });
    it("with optional compose files", () => {
      let image = new Image("my-image", { files: ["docker-compose.yml"] });
      let fileFlags = image._getFileFlags();
      expect(fileFlags.length).toEqual(1);

      image = new Image("my-image", {
        files: [
          "docker-compose.yml",
          "docker-compose.development.yml",
          "docker-compose.options.yml",
        ],
      });
      fileFlags = image._getFileFlags();
      expect(fileFlags.length).toEqual(3);
    });
  });
});
