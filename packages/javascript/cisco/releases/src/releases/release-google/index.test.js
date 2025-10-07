const GoogleRelease = require("./index");

const PROJECT_ID = "Google Project ID";

xtest("requires baseName", () => {
  expect(new GoogleRelease()).toThrow("projectId required");
});

it("constructs an OpenShift release", () => {
  const release = new GoogleRelease(PROJECT_ID);
  expect(release.baseName).toBe(PROJECT_ID);
});
