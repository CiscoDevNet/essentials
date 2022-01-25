const { Release, GoogleRelease, OpenShiftRelease } = require("./index");

it("imports all release types", () => {
  expect(Release).toBeTruthy();
  expect(GoogleRelease).toBeTruthy();
  expect(OpenShiftRelease).toBeTruthy();
});
