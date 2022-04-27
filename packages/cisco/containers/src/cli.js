#!/usr/bin/env node

const { execSync } = require("child_process");
const DockerImage = require("./docker-image");
const { program } = require("commander");

const COMPOSE_FILES = ["docker-compose.yml", "docker-compose.non-dev.yml"];
const EXEC_SYNC_OPTIONS = { stdio: "inherit" };
const VERSION = "0.1.0";
const OPTIONS = {
  PROJECT: [
    "-p, --project <project>",
    "project containing the image, e.g., library",
  ],
  REGISTRY: ["-r, --registry <registry>", "global repository, e.g., docker.io"],
  TAG: ["-t, --tag <tag>", "image tag, e.g., latest, 1.0.0"],
};

main();

function main() {
  program.version(VERSION);

  program
    .command("build <image>")
    .description("build image")
    .option(...OPTIONS.TAG)
    .option(...OPTIONS.PROJECT)
    .option(...OPTIONS.REGISTRY)
    .action(buildImage);

  program
    .command("run <image> [service]")
    .description("run image")
    .option(...OPTIONS.TAG)
    .option(...OPTIONS.PROJECT)
    .option(...OPTIONS.REGISTRY)
    .action(startContainer);

  program.parse();
}

function buildImage(image, options) {
  const dockerImage = getDockerImage(image, options);
  const envVar = getImageEnvVar(dockerImage);
  const buildCommand = [envVar, dockerImage.buildCommand].join(" ");
  execSync(buildCommand, EXEC_SYNC_OPTIONS);
}

function startContainer(image, service, options) {
  const dockerImage = getDockerImage(image, options);
  const envVar = getImageEnvVar(dockerImage);
  const startCommand = [envVar, dockerImage.getRunCommand(service)].join(" ");
  execSync(startCommand, EXEC_SYNC_OPTIONS);
}

function getDockerImage(image, options) {
  const { tag, registry, project } = options;
  return new DockerImage(image, {
    tag,
    registry,
    project,
    files: COMPOSE_FILES,
  });
}

function getImageEnvVar(dockerImage) {
  return `IMAGE=${dockerImage.addressableName}`;
}
