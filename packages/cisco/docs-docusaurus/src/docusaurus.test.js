const Docusaurus = require("./docusaurus");

const MAIN_URL = "https://cisco.com";

function expectDefaultConfig(docusaurus) {
  const { basicConfig } = docusaurus;
  expect(basicConfig.url).toBe(MAIN_URL);
  expect(basicConfig.organizationName).toBe("cisco");
  expect(basicConfig.projectName).toBe("project");

  expect(basicConfig.title).toBe("My Site");
  expect(basicConfig.tagline).toBeUndefined();

  expect(docusaurus.repoPath).toBe("https://github.com/cisco/project");
  expect(docusaurus.repoEditPath).toContain("edit");
  expect(docusaurus.repoEditPath).toBe(
    "https://github.com/cisco/project/edit/main"
  );

  expect(docusaurus.repoTreePath).toContain("tree");
  expect(docusaurus.repoTreePath).toBe(
    "https://github.com/cisco/project/tree/main"
  );

  expect(docusaurus.repoBlobPath).toContain("blob");
  expect(docusaurus.repoBlobPath).toBe(
    "https://github.com/cisco/project/blob/main"
  );
}

describe("Docusaurus", () => {
  describe("creates standard config", () => {
    it("with no config", () => {
      const docusaurus = new Docusaurus("cisco", "project", MAIN_URL);
      expectDefaultConfig(docusaurus);
    });

    it("with empty config", () => {
      const docusaurus = new Docusaurus("cisco", "project", MAIN_URL, {});
      expectDefaultConfig(docusaurus);
    });
  });

  it("creates custom config", () => {
    const customConfig = {
      repoBranch: "fix",
      repoUrlBase: "https://gitlab.com",
      repoDirPath: "packages/gve/digital-garden",
      title: "Cisco Essentials",
      tagline: "Build better software",
    };
    const docusaurus = new Docusaurus(
      "cisco",
      "project",
      MAIN_URL,
      customConfig
    );

    const { basicConfig } = docusaurus;
    expect(basicConfig.url).toBe(MAIN_URL);
    expect(basicConfig.organizationName).toBe("cisco");
    expect(basicConfig.projectName).toBe("project");

    expect(basicConfig.title).toBe(customConfig.title);
    expect(basicConfig.tagline).toBe(customConfig.tagline);

    expect(docusaurus.repoPath).toBe(
      `${customConfig.repoUrlBase}/cisco/project`
    );
    expect(docusaurus.repoEditPath).toContain("edit");
    expect(docusaurus.repoEditPath).toBe(
      `${customConfig.repoUrlBase}/cisco/project/edit/${customConfig.repoBranch}/${customConfig.repoDirPath}`
    );

    expect(docusaurus.repoTreePath).toContain("tree");
    expect(docusaurus.repoTreePath).toBe(
      `${customConfig.repoUrlBase}/cisco/project/tree/${customConfig.repoBranch}/${customConfig.repoDirPath}`
    );
  });
});
