# !/bin/bash

# Description: Unpublish all @cisco/* packages from the npm registry.
# Author: Matt Norris <matnorri@cisco.com>
#
# This script forcefully unpublishes a list of @cisco scoped packages from the npm registry.
# - It is intended for emergency or cleanup scenarios where published packages must be removed.
# - The --force flag is required by npm to unpublish packages that are older than 72 hours or have multiple versions.
#
# Usage:
#   ./scripts/npm-unpublish.sh
#
# Important Notes:
# - Unpublishing packages is a destructive operation and cannot be undone.
# - Use with extreme caution, especially for public packages, as it may break dependent projects.
# - For more information, see:
#   https://docs.npmjs.com/cli/v8/commands/npm-unpublish
#   https://stackoverflow.com/a/61231856/154065
#
# Example:
#   To unpublish all listed packages, simply run the script:
#     ./scripts/npm-unpublish.sh
#
# See also:
#   - scripts/npm-audit-fix.sh for automated dependency fixes

npm unpublish @cisco/analytics --force
npm unpublish @cisco/bot-commands --force
npm unpublish @cisco/bot-factory --force
npm unpublish @cisco/bot-middleware --force
npm unpublish @cisco/cards --force
npm unpublish @cisco/core --force
npm unpublish @cisco/google --force
npm unpublish @cisco/releases --force
npm unpublish @cisco/salesforce --force
