/**
 * Backup directories and files as an archive.
 * @constant
 * @see https://serverfault.com/a/141778/106402
 */
const ARCHIVE = "a";

/**
 * Perform a dry run.
 * @constant
 */
const DRY_RUN = "n";

/**
 * Ignore timestamps to force overwriting similar destination files.
 * @constant
 */
const IGNORE_TIMESTAMPS = "I";

/**
 * Use these options for rysnc backup.
 * @constant
 */
const RSYNC_OPTIONS = {
  ARCHIVE,
  DRY_RUN,
  IGNORE_TIMESTAMPS,
};

module.exports = { RSYNC_OPTIONS };
