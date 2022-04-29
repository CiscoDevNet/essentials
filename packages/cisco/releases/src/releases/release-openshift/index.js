/**
 * @file A release specific to OpenShift.
 * @author Matt Norris <matnorri@cisco.com>
 */

const debug = require("debug")("releases:openshift");

const colors = require("colors/safe");
const { execSync } = require("child_process");
const path = require("path");
const url = require("url");

const Release = require("../release");

const {
  BOT_URL,
  EXEC_SYNC_OPTIONS,
  DEPLOYMENT,
  DEPLOYMENT_TEMPLATE,
  HOSTNAME,
  ROUTE,
  ROUTE_TEMPLATE,
  SECRET,
  SERVICE,
} = require("./config");

const { PORT, SERVICE_TEMPLATE } = require("../../config");

/**
 * Deployment kinds
 */
const DEPLOYMENT_KINDS = {
  KUBERNETES: "Deployment",
  OPENSHIFT: "DeploymentConfig",
};

const { DeploymentError } = require("./errors");

class OpenShiftRelease extends Release {
  constructor(projectName, imagePullSecret, config) {
    super(projectName, config);
    this.imagePullSecret = imagePullSecret;

    if (!this.projectName) {
      throw new Error("projectName required to create a release.");
    }

    if (!this.imagePullSecret) {
      throw new Error("imagePullSecret required to create a release.");
    }

    const { hostName = HOSTNAME, deploymentKind = DEPLOYMENT_KINDS.OPENSHIFT } =
      this.config;

    this.hostName = hostName;
    this.deploymentKind = deploymentKind;

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
    const deploymentTemplatePath = path.join(releasesDir, DEPLOYMENT_TEMPLATE);
    const isDeploymentConfig =
      this.deploymentKind === DEPLOYMENT_KINDS.OPENSHIFT;

    /**
     * Label to set in all resources for this application.
     */
    const labels = `-l app=${this.name}`;

    const generateTemplateCommandParts = [
      "oc",
      "new-app",
      this.fullImageName,
      variables.join(" "),
      labels,
      `--as-deployment-config=${isDeploymentConfig}`,
      "--dry-run=true",
      `-o yaml > ${deploymentTemplatePath}`,
    ].filter(Boolean);

    const generateTemplateCommand = generateTemplateCommandParts.join(" ");
    execSync(generateTemplateCommand);

    debug("reading template: ", deploymentTemplatePath);
    const deploymentTemplate = Release.read(deploymentTemplatePath);

    debug(`adding secret ${this.imagePullSecret} to deployment...`);
    const deploymentData = this._getDeploymentData(deploymentTemplate);
    if (!deploymentData) {
      throw new DeploymentError("deployment data not found");
    }
    const { spec } = deploymentData.spec.template;
    spec.imagePullSecrets = [{ name: this.imagePullSecret }];

    const deploymentPath = path.join(releasesDir, DEPLOYMENT);
    debug("writing config: ", deploymentPath);
    Release.write(deploymentTemplate, deploymentPath);

    console.log(colors.green("Created Deployment configuration.\n"));
  }

  /**
   * Returns the deployment configuration of the given deployment template.
   * @param {Object} deploymentTemplate
   * @returns {Object} deployment config
   */
  _getDeploymentData(deploymentTemplate) {
    const { items = [] } = deploymentTemplate;
    const deploymentConfigs = items.filter((item) => {
      const { kind: deploymentKind } = item;
      return deploymentKind === this.deploymentKind;
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
    const routeTemplatePath = path.join(releasesDir, ROUTE_TEMPLATE);

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

    const routeConfig = path.join(releasesDir, ROUTE);
    Release.write(contents, routeConfig);

    const instructions = [
      `${colors.green("Created Route configuration.")}`,
      "",
      "You can now deploy this route.",
      "",
      `${colors.yellow(
        "WARN: You will need to update and provision the route policy after deploying."
      )}`,
      "",
    ];

    console.log(instructions.join("\n"));
  }

  buildService(port = PORT) {
    console.log("Creating Service configuration...");
    const releasesDir = Release.createReleasesDir();
    const serviceTemplatePath = path.join(releasesDir, SERVICE_TEMPLATE);

    const commandParts = [
      "oc create service clusterip",
      this.name,
      `--tcp=${port}`,
      "--dry-run=server",
      `-o yaml > ${serviceTemplatePath}`,
    ];

    try {
      // Read the dry-run to use as a template.
      execSync(commandParts.join(" "));
      const service = Release.read(serviceTemplatePath);

      // Update the values.
      const { spec } = service;
      spec.ports[0].name = `${port}-tcp`;
      spec.selector[this.deploymentKind.toLowerCase()] = this.name;

      // Write the deployment file.
      const servicePath = path.join(releasesDir, SERVICE);
      Release.write(service, servicePath);

      const instructions = [
        `${colors.green("Created Service configuration file.")}`,
        "",
        "You can now deploy this service.",
        "",
      ];

      console.log(instructions.join("\n"));
    } catch (error) {
      const { message = "" } = error;
      const _message = message.trim();
      const doesExist = _message.toLowerCase().includes("already exists");
      if (doesExist) {
        console.warn(colors.yellow(_message));
      } else {
        console.error(colors.red(_message));
      }
    }
  }

  async release() {
    this.activate();
    console.log();

    const secretPath = path.join(process.cwd(), SECRET);
    console.log("Releasing secret:", secretPath);
    await this._releaseFile(secretPath);

    debug("releases directory:", this.releasesDir);
    const deploymentPath = path.join(this.releasesDir, DEPLOYMENT);
    console.log("Releasing deployment:", deploymentPath);
    await this._releaseFile(deploymentPath);
  }

  async releaseService() {
    this.activate();
    console.log();

    const servicePath = path.join(this.releasesDir, SERVICE);
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

    const routePath = path.join(this.releasesDir, ROUTE);
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
      fileResult = await Release.spawn("oc", createFileArgs);
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
        fileResult = await Release.spawn("oc", updateFileArgs);
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
}

module.exports = OpenShiftRelease;