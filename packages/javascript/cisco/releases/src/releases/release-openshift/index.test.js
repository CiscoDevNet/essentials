const OpenShiftRelease = require("./index");

const BASE_NAME = "base name, e.g., package name";
const IMAGE_PULL_SECRET = "image pull secret file name";

xtest("requires baseName", () => {
  expect(new OpenShiftRelease()).toThrow("baseName required");
});

xtest("requires imagePullSecret", () => {
  expect(new OpenShiftRelease(BASE_NAME)).toThrow("imagePullSecret required");
});

it("constructs an OpenShift release", () => {
  const release = new OpenShiftRelease(BASE_NAME, IMAGE_PULL_SECRET);
  expect(release.baseName).toBe(BASE_NAME);

  // Default registry
  expect(release.registry).toBe("docker.io");
});
