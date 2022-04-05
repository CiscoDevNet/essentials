const OpenShiftRelease = require("./index");

const PROJECT_NAME = "project name or project ID";
const IMAGE_PULL_SECRET = "image pull secret file name";

xtest("requires projectName", () => {
  expect(new OpenShiftRelease()).toThrow("projectName required");
});

xtest("requires imagePullSecret", () => {
  expect(new OpenShiftRelease(PROJECT_NAME)).toThrow(
    "imagePullSecret required"
  );
});

it("constructs an OpenShift release", () => {
  const release = new OpenShiftRelease(PROJECT_NAME, IMAGE_PULL_SECRET);
  expect(release.projectName).toBe(PROJECT_NAME);
});
