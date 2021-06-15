/**
 * @file A release specific to OpenShift.
 * @author Matt Norris <matnorri@cisco.com>
 */

const debug = require("debug")("releases:openshift");

const colors = require("colors/safe");
const { execSync, spawn } = require("child_process");
const path = require("path");
const url = require("url");

const Release = require("../release");

const {
  BOT_URL,
  COMMAND_EVENTS,
  EXEC_SYNC_OPTIONS,
  PORT,
  RELEASES_DEPLOYMENT,
  RELEASES_DEPLOYMENT_TEMPLATE,
  RELEASES_IMAGE_PULL_SECRET,
  RELEASES_PROJECT_NAME,
  RELEASES_ROUTE,
  RELEASES_ROUTE_TEMPLATE,
  RELEASES_SECRET,
  RELEASES_SERVICE,
} = require("./config");

const { DeploymentConfigError } = require("./errors");

class OpenShiftRelease extends Release {
  constructor(config) {
    super(config);

    const { projectName = RELEASES_PROJECT_NAME } = this.config;

    // Require an explicit project name so that code isn't released
    // to the implicit, active project.
    if (!projectName) {
      throw new Error("projectName or projectId is required.");
    }

    this.projectName = projectName;

    debug("initiated");
  }

  activate() {
    execSync(`oc project ${this.projectName}`, EXEC_SYNC_OPTIONS);
    return this.projectName;
  }

  buildDeployment() {
    console.log("Creating Deployment configuration...");
    debug("getting environment variables...");
    debug(
      `found ${Object.values(this.envVariables).length} environment variables`
    );

    // Include any valid environment variables in the deployment configuration.
    const variables = [];
    for (let [variable, value] of Object.entries(this.envVariables)) {
      if (value) {
        // Escape the special character `$` so that the later call to
        // the `oc` command will not strip the character from the string.
        const escapedValue = value.replace("$", "\\$");
        variables.push(`-e ${variable}="${escapedValue}"`);
      }
    }

    // Generate the template.
    const releasesDir = Release.createReleasesDir();
    const deploymentTemplatePath = path.join(
      releasesDir,
      RELEASES_DEPLOYMENT_TEMPLATE
    );
    const generateTemplateCommandParts = [
      "oc",
      "new-app",
      this.fullImageName,
      variables.join(" "),
      "--dry-run=true",
      `-o yaml > ${deploymentTemplatePath}`,
    ];

    const generateTemplateCommand = generateTemplateCommandParts.join(" ");
    execSync(generateTemplateCommand);

    debug("reading template: ", deploymentTemplatePath);
    const deploymentTemplate = Release.read(deploymentTemplatePath);

    debug(
      `adding secret ${RELEASES_IMAGE_PULL_SECRET} to deployment config...`
    );
    const deploymentConfig = this._getDeploymentConfig(deploymentTemplate);
    if (!deploymentConfig) {
      throw new DeploymentConfigError("deployment config not found");
    }
    const { spec } = deploymentConfig.spec.template;
    spec.imagePullSecrets = [{ name: RELEASES_IMAGE_PULL_SECRET }];

    const deploymentPath = path.join(releasesDir, RELEASES_DEPLOYMENT);
    debug("writing config: ", deploymentPath);
    Release.write(deploymentTemplate, deploymentPath);

    console.log(colors.green("Created Deployment configuration.\n"));

    this.buildService();

    const instructions = [
      `Deploy these configurations with:`,
      "",
      `  npm run release`,
      "",
    ];

    console.log(instructions.join("\n"));
  }

  /**
   * Returns the deployment configuration of the given deployment template.
   * @param {Object} deploymentTemplate
   * @returns {Object} deployment config
   */
  _getDeploymentConfig(deploymentTemplate) {
    const { items = [] } = deploymentTemplate;
    const deploymentConfigs = items.filter((item) => {
      const { kind: itemType } = item;
      const isDeploymentConfig =
        itemType === "Deployment" || itemType === "DeploymentConfig";
      return isDeploymentConfig;
    });
    return deploymentConfigs[0];
  }

  buildRoute() {
    const botUrl = BOT_URL;
    const hostname = url.parse(botUrl).hostname;
    debug(`hostname ${hostname} from URL ${botUrl}`);

    const name = this.name;
    const route = this.environment || name || "route";
    const service = `svc/${name}`;

    const releasesDir = Release.createReleasesDir();
    const routeTemplatePath = path.join(releasesDir, RELEASES_ROUTE_TEMPLATE);

    const exposeRouteCommandParts = [
      "oc expose",
      service,
      `--name=${route}`,
      `--hostname=${hostname}`,
      "--dry-run=true",
      `-o yaml > ${routeTemplatePath}`,
    ];
    const exposeRouteCommand = exposeRouteCommandParts.join(" ");
    execSync(exposeRouteCommand);

    const contents = Release.read(routeTemplatePath);

    // Secure route for serving certificates.
    const { spec } = contents;
    spec.tls = {
      termination: "edge",
      insecureEdgeTerminationPolicy: "None",
    };

    const routeConfig = path.join(releasesDir, RELEASES_ROUTE);
    Release.write(contents, routeConfig);

    const instructions = [
      `${colors.green("Created Route configuration.")} Deploy it with:`,
      "",
      "  npm run release:route",
      "",
      `${colors.yellow(
        "WARN: You will need to update and provision the route policy after deploying."
      )}`,
      "",
    ];

    console.log(instructions.join("\n"));
  }

  buildService() {
    console.log("Creating Service configuration...");
    const name = this.name;
    const port = PORT;

    const serviceTemplate = {
      apiVersion: "v1",
      items: [
        {
          apiVersion: "v1",
          kind: "Service",
          metadata: {
            labels: {
              app: name,
            },
            name,
          },
          spec: {
            ports: [
              { name: `${port}-tcp`, port, protocol: "TCP", targetPort: port },
            ],
            selector: {
              app: name,
              deploymentconfig: name,
            },
          },
          status: {
            loadBalancer: {},
          },
        },
      ],
      kind: "List",
      metadata: {},
    };

    const releasesDir = Release.createReleasesDir();
    const servicePath = path.join(releasesDir, RELEASES_SERVICE);
    Release.write(serviceTemplate, servicePath);
    console.log(colors.green("Created Service configuration.\n"));
  }

  async release() {
    this.activate();
    console.log();

    const secretPath = path.join(process.cwd(), RELEASES_SECRET);
    console.log("Releasing secret:", secretPath);
    await this._releaseFile(secretPath);

    debug("releases directory:", this.releasesDir);
    const deploymentPath = path.join(this.releasesDir, RELEASES_DEPLOYMENT);
    console.log("Releasing deployment:", deploymentPath);
    await this._releaseFile(deploymentPath);

    const servicePath = path.join(this.releasesDir, RELEASES_SERVICE);
    console.log("Releasing service:", servicePath);
    await this._releaseFile(servicePath);
  }

  async _releaseFile(filename) {
    debug("releasing file:", filename);
    try {
      const result = await this._update(filename);
      console.log(colors.green(result.toString()));
    } catch (error) {
      const { message = "" } = error;
      const isWarning = message.toLowerCase().includes("warning");
      if (isWarning) {
        console.warn(colors.yellow(message.trim()));
        console.log(colors.green("Done."));
        console.log();
      } else {
        console.error(colors.red(message));
      }
    }
  }

  async releaseRoute() {
    this.activate();
    console.log();

    const routePath = path.join(this.releasesDir, RELEASES_ROUTE);
    console.log("Releasing route:", routePath);
    await this._releaseFile(routePath);
  }

  async _update(remoteFile) {
    let hasRemoteFile = false;
    let fileResult;
    let errorMessage;

    /**
     * Initial version did not use the --save-config option.
     * However, is better because later you can "apply" changes
     * to the remote file rather than force its overwrite with "replace".
     *
     * A simple "apply" may work as well.
     *
     * @see https://www.timcosta.io/kubernetes-service-invalid-clusterip-or-resourceversion/
     * @see https://stackoverflow.com/a/59662696/154065
     */
    const createFileArgs = ["create", "-f", remoteFile, "--save-config"];

    // Create the file on the server.
    try {
      fileResult = await this._spawn("oc", createFileArgs);
    } catch (createFileErrorMessage) {
      errorMessage = createFileErrorMessage;
      hasRemoteFile = createFileErrorMessage.includes("AlreadyExists");
      debug("create file error:", createFileErrorMessage);
    }

    // If the file exists on the server, update it.
    if (!fileResult && hasRemoteFile) {
      /**
       * Initial version used: oc replace -f ${remoteFile}
       * But it was not necessary to "replace" the file, just update it.
       */
      const updateFileArgs = ["apply", "-f", remoteFile];

      try {
        fileResult = await this._spawn("oc", updateFileArgs);
      } catch (udpateFileErrorMessage) {
        errorMessage = udpateFileErrorMessage;
        debug("update file error:", errorMessage);
      }
    }

    // If the server file was not created or updated, throw an error.
    if (!fileResult) {
      throw new Error(errorMessage);
    }

    return fileResult;
  }

  /**
   * Runs the given command and its args inside a Promise
   * so it can be unpacked later.
   * @param {String} commandName - the command name
   * @param {Array[String]} args - the command arguments
   * @see https://stackoverflow.com/a/35896832/154065
   * @returns {Promise} string output
   */
  _spawn(commandName, args) {
    return new Promise((resolve, reject) => {
      let stdoutData = "";
      let stderrData = "";

      // Run the command.
      const command = spawn(commandName, args);

      // Gather normal output.
      command.stdout.on(COMMAND_EVENTS.DATA, (data) => {
        stdoutData += data;
      });

      // Gather errors.
      command.stderr.on(COMMAND_EVENTS.DATA, (data) => {
        stderrData += data;
      });

      // Reject if there is an error.
      command.on(COMMAND_EVENTS.ERROR, (err) => {
        reject(err);
      });

      // When finished, reject if there are errors. Resolve otherwise.
      command.on(COMMAND_EVENTS.CLOSE, () => {
        if (stderrData) {
          reject(stderrData);
        } else {
          resolve(stdoutData);
        }
      });
    });
  }
}

module.exports = OpenShiftRelease;
