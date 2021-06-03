const debug = require("debug")("bridge");

const forceBoolean = require("force-boolean").default;
const fs = require("fs");
const lodashUpdate = require("lodash.update");
const lodashUnion = require("lodash.union");
const parseGitIgnore = require("parse-gitignore");
const path = require("path");
const Rsync = require("rsync");

const {
  CopyError,
  DirectoryError,
  GitIgnoreError,
  ParseError,
  ProjectError,
  RollbackError,
  SourceIsDestError,
} = require("./errors");

/**
 * Configuration options
 * @typedef {Object} BridgeConfig
 * @property {boolean} dryRun - perform a dry run
 */

/**
 * Default configuration
 * @type {BridgeConfig}
 */
const DEFAULT_CONFIG = { dryRun: false };

const GIT_IGNORE = ".gitignore";
const MONOREPO_CONFIG = "lerna.json";
const { RSYNC_OPTIONS } = require("./constants");

class Bridge {
  /**
   * Creates a new Bridge from the source to the destination project.
   * @param {String} source - the source directory
   * @param {String} project - the destination project directory
   * @param {BridgeConfig} config - configuration options
   */
  constructor(source, project, config = DEFAULT_CONFIG) {
    this.source = source;
    this.project = project;

    const { dryRun = false } = config;
    this.dryRun = dryRun;
  }

  get dryRun() {
    return this._dryRun;
  }

  set dryRun(shouldDoDryRun) {
    this._dryRun = forceBoolean(shouldDoDryRun);
  }

  get source() {
    return this._source;
  }

  /**
   * Sets the source directory.
   * @throws {DirectoryError}
   */
  set source(sourcePath) {
    const fullSourcePath = path.resolve(sourcePath);
    if (!Bridge.isDirectory(fullSourcePath)) {
      throw new DirectoryError(fullSourcePath);
    }
    this._source = sourcePath;
  }

  get project() {
    return this._project;
  }

  /**
   * Sets the project directory.
   * @throws {DirectoryError}
   * @throws {ProjectError}
   */
  set project(projectDir) {
    const projectPath = path.resolve(projectDir);
    if (!Bridge.isDirectory(projectPath)) {
      throw new DirectoryError(projectPath);
    }

    if (!Bridge.isMonoRepo(projectPath)) {
      const message = `${projectPath} is not a monorepo`;
      throw new ProjectError(message);
    }

    this._project = projectDir;
  }

  get destination() {
    return path.join(this.project, "packages");
  }

  /**
   * Returns true if the project is a valid monorepo, false otherwise.
   * @param {String} project - the project directory
   * @returns {boolean} true if the project is a valid monorepo, false otherwise
   */
  static isMonoRepo(project) {
    const projectPath = path.resolve(project);
    if (!Bridge.isDirectory(projectPath)) {
      return false;
    }

    const isPackage = fs.existsSync(path.join(projectPath, "package.json"));
    const hasMonoRepoConfigFile = fs.existsSync(
      path.join(projectPath, MONOREPO_CONFIG)
    );

    return isPackage && hasMonoRepoConfigFile;
  }

  /**
   * Copies files from the source directory to the project destination directory.
   * @returns {String} the destination path where files were copied
   * @throws {SourceIsDestError}
   */
  async copy() {
    this._debugDryRun();

    // Check that the source and destination directories are not the same.
    const sourceBaseName = path.basename(this.source);
    const ultimateDest = path.resolve(
      path.join(this.destination, sourceBaseName)
    );
    debug("ultimate destination:", ultimateDest);
    if (path.resolve(this.source) === ultimateDest) {
      throw new SourceIsDestError();
    }

    return await Bridge.copy(this.source, this.destination, this.dryRun);
  }

  /**
   * Prints standard dry run debug message.
   * @private
   */
  _debugDryRun() {
    const DRY_RUN = "\n=== Dry run ===\n";
    const NOT_DRY_RUN = "\n!!! WARN: NOT a dry run !!!\n";
    debug(this.dryRun ? DRY_RUN : NOT_DRY_RUN);
  }

  /**
   * Adds destination and backup file paths to .gitignore
   * so the files are not committed to the project repo.
   */
  async gitIgnore() {
    this._debugDryRun();

    let rawFile;
    let parsed;
    const gitIgnorePath = path.join(this.project, GIT_IGNORE);

    // Read the .gitignore file.
    try {
      rawFile = fs.readFileSync(gitIgnorePath, "utf8");
    } catch (error) {
      throw new GitIgnoreError(error.message);
    }

    // Back it up.
    let backupPath;
    try {
      backupPath = `${gitIgnorePath}.bak`;
      if (!this.dryRun) {
        fs.writeFileSync(backupPath, rawFile, "utf8");
      }
      debug(`${gitIgnorePath} backed up to ${backupPath}`);
    } catch (error) {
      throw new GitIgnoreError(error.message);
    }

    // Parse it.
    try {
      parsed = parseGitIgnore(rawFile);
      debug(`parsed: ${gitIgnorePath}; ignoring ${parsed.length} paths`);
    } catch (error) {
      throw new ParseError(error.message);
    }

    // Check if the destination path is already ignored.
    // If it is, do nothing. If it's not ignored, rewrite .gitignore so that it is.
    const sourceBaseName = path.basename(this.source);
    const destPath = path.join(this.destination, sourceBaseName);
    const relativeDestPath = path.relative(this.project, destPath);
    const isIgnored = !!parsed.filter((line) => {
      return line.startsWith(relativeDestPath);
    }).length;

    debug(`"${relativeDestPath}" is already ignored: ${isIgnored}`);

    if (!isIgnored) {
      try {
        if (!this.dryRun) {
          fs.appendFileSync(
            gitIgnorePath,
            "\n# External bridged packages and backup files\n"
          );
          fs.appendFileSync(gitIgnorePath, "# Written by @gve/bridge\n");
          fs.appendFileSync(gitIgnorePath, `${relativeDestPath}\n`);
          fs.appendFileSync(gitIgnorePath, `${backupPath}\n`);
          fs.appendFileSync(gitIgnorePath, `${MONOREPO_CONFIG}.bak\n`);
        }
        debug(`rewritten: ${gitIgnorePath}`);
      } catch (error) {
        const { original } = this._rollbackFile(gitIgnorePath, backupPath);
        debug(`rolled back to original file: ${original}`);
        throw new GitIgnoreError(error.message);
      }
    }
  }

  /**
   * Rollback information
   * @typedef {Object} Rollback
   * @param {String} original - the original file path
   * @param {String} backup - the backup file path
   */

  /**
   * Rolls back the file to the original copy.
   * @param {*} original - the original file path
   * @param {*} backup - the backup file path
   * @returns {Rollback} rollback information
   * @throws {RollbackError}
   */
  _rollbackFile(original, backup) {
    try {
      if (!this.dryRun) {
        const backupFile = fs.readFileSync(backup, "utf8");
        fs.writeFileSync(original, backupFile, "utf8");
      }
    } catch (_) {
      throw new RollbackError(original, backup);
    }

    return { original, backup };
  }

  /**
   * Adds destination file paths to the monorepo config.
   * These files will be ignored when publishing packages.
   */
  async publishIgnore() {
    const projectConfigPath = path.join(this.project, MONOREPO_CONFIG);

    // Read the project config file.
    let rawFile;
    let parsed;
    try {
      rawFile = fs.readFileSync(projectConfigPath, "utf8");
      debug(rawFile);
      parsed = JSON.parse(rawFile);
    } catch (_) {
      const message = `could not read ${projectConfigPath}`;
      throw new ProjectError(message);
    }

    // Back it up.
    let backupPath;
    try {
      backupPath = `${projectConfigPath}.bak`;
      if (!this.dryRun) {
        fs.writeFileSync(backupPath, rawFile, "utf8");
      }
      debug(`${projectConfigPath} backed up to ${backupPath}`);
    } catch (error) {
      throw new ProjectError(error.message);
    }

    const sourceBaseName = path.basename(this.source);
    const destPath = path.join(this.destination, sourceBaseName);
    const relativeDestPath = path.relative(this.project, destPath);

    // Update the config file to bootstrap the bridged packages.
    const PARSED_PACKAGES_PATH = "packages";
    lodashUpdate(parsed, PARSED_PACKAGES_PATH, (packages) => {
      return lodashUnion(packages, [`${relativeDestPath}/*`]);
    });

    // Update the config file to ignore changes to the bridged packages.
    const PARSED_IGNORE_PATH = "command.publish.ignoreChanges";
    lodashUpdate(parsed, PARSED_IGNORE_PATH, (ignoreChanges) => {
      return lodashUnion(ignoreChanges, [`${relativeDestPath}/*`]);
    });

    debug(`updated ignoreChanges:`, parsed.command.publish.ignoreChanges);

    try {
      if (!this.dryRun) {
        fs.writeFileSync(projectConfigPath, JSON.stringify(parsed));
      }
      debug(`rewritten: ${projectConfigPath}`);
    } catch (error) {
      const { original } = this._rollbackFile(projectConfigPath, backupPath);
      debug(`rolled back to original file: ${original}`);
      throw new ProjectError(error.message);
    }
  }

  /**
   * Copies files from the source to the destination.
   *
   * @returns {String} the destination path where files were copied
   */
  static async copy(source, destination, dryRun) {
    // Paths must be resolved or rsync will not place the source directory
    // as a subdirectory of the destination directory.
    const resolvedSource = path.resolve(source);
    const resolvedDest = path.resolve(destination);

    debug("copying from:", resolvedSource);
    debug("copying to:", resolvedDest);

    try {
      const result = await this.rsync(resolvedSource, resolvedDest, dryRun);
      debug("command executed:", result.command);
      debug("command exited with:", result.code);
    } catch (error) {
      throw new CopyError(error.message);
    }

    const ultimateDest = path.join(destination, path.basename(source));
    return ultimateDest;
  }

  static async rsync(source, destination, dryRun) {
    const { ARCHIVE, DRY_RUN, IGNORE_TIMESTAMPS } = RSYNC_OPTIONS;
    const rsyncCommand = new Rsync()
      .flags(ARCHIVE, IGNORE_TIMESTAMPS)
      .exclude([".git", "node_modules"])
      .source(source)
      .destination(destination);

    if (dryRun) {
      rsyncCommand.flags(DRY_RUN);
    }

    return new Promise((resolve, reject) => {
      rsyncCommand.execute((error, code, command) => {
        if (error) {
          reject(error);
        }

        resolve({ code, command });
      });
    });
  }

  /**
   * Returns true if the given path is a directory, false otherwise.
   * @param {String} dir - the directory path
   * @returns {boolean} true if the given path is a directory, false otherwise
   *
   * @see https://stackoverflow.com/a/32749571/154065
   */
  static isDirectory(dir) {
    try {
      return fs.statSync(dir).isDirectory();
    } catch (_) {
      return false;
    }
  }
}

module.exports = Bridge;
