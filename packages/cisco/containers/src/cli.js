#!/usr/bin/env node

const { execSync } = require("child_process");
const Image = require("./image");
const { program } = require("commander");

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

function buildImage(imageBaseName, options) {
  const image = getImage(imageBaseName, options);
  const envVar = getImageEnvVar(image);
  const buildCommand = [envVar, image.buildCommand].join(" ");
  execSync(buildCommand, EXEC_SYNC_OPTIONS);
}

function startContainer(imageBaseName, service, options) {
  const image = getImage(imageBaseName, options);
  const envVar = getImageEnvVar(image);
  const startCommand = [envVar, image.getRunCommand(service)].join(" ");
  execSync(startCommand, EXEC_SYNC_OPTIONS);
}

function getImage(imageBaseName, options) {
  const { tag, registry, project, files } = options;
  return new Image(imageBaseName, {
    tag,
    registry,
    project,
    files,
  });
}

function getImageEnvVar(image) {
  return `IMAGE=${image.addressableName}`;
}
