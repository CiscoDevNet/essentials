const path = require("path");

const {
  env,

  NAME,
  VERSION,

  BOT_URL,

  NODE_ENV,
  PORT,

  NPM_REGISTRY,
  NPM_USERNAME,
  NPM_PASSWORD,

  RELEASES_DIRECTORY,

  DEPLOYMENT,
  DEPLOYMENT_TEMPLATE,

  ROUTE,
  ROUTE_TEMPLATE,

  SECRET,
  SERVICE,

  PLATFORM,
  HOSTNAME,
  ORG,
} = require("./config");

it("has default config values", () => {
  expect(env).toBeTruthy();
  expect(BOT_URL).toBeUndefined();
  expect(PORT).toBe("3000");

  expect(NPM_REGISTRY).toBe("https://registry.npmjs.org");
  expect(NPM_USERNAME).toBeUndefined();
  expect(NPM_PASSWORD).toBeUndefined();

  expect(PLATFORM).toBe("docker");
  expect(HOSTNAME).toBe("docker.io");
  expect(ORG).toBe("library");

  const releasesDirBasename = path.basename(RELEASES_DIRECTORY);
  expect(releasesDirBasename).toBe(".releases");

  expect(DEPLOYMENT).toBe("deployment.yml");
  expect(DEPLOYMENT_TEMPLATE).toBe("deployment-template.yml");
  expect(ROUTE).toBe("route.yml");
  expect(ROUTE_TEMPLATE).toBe("route-template.yml");
  expect(SECRET).toBe("secret.yml");
  expect(SERVICE).toBe("service.yml");

  // Config picks up this package's name and version by default.
  expect(NAME).toBe("releases");
  expect(VERSION).toBeTruthy(); // e.g., 0.1.2

  // Jest sets the NODE_ENV to "test".
  expect(NODE_ENV).toBe("test");
});
