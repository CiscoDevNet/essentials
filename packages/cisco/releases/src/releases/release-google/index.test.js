const GoogleRelease = require("./index");

const PROJECT_ID = "Google Project ID";

xtest("requires projectName", () => {
  expect(new GoogleRelease()).toThrow("projectId required");
});

it("constructs an OpenShift release", () => {
  const release = new GoogleRelease(PROJECT_ID);
  expect(release.projectName).toBe(PROJECT_ID);
});
