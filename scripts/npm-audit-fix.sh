# !/bin/bash

# Description: Run npm audit and attempt to automatically fix vulnerabilities for packages matching the given filter.
# Author: Matt Norris <matnorri@cisco.com>
#
# This script uses Lerna to execute `npm audit fix` across multiple packages in the monorepo.
# - By default, it targets packages matching the filter "@cisco/*" and fixes only production dependencies.
# - You can specify a different package filter or environment (prod/dev) as arguments.
#
# About npm audit:
# - `npm audit` checks your dependencies for known security vulnerabilities.
# - `npm audit fix` attempts to automatically update dependencies to resolve vulnerabilities.
# - Use `--only=prod` (default) to audit only production dependencies, or `--only=dev` for development dependencies.
# - Not all vulnerabilities can be fixed automatically; manual intervention may be required for some issues.
#
# Usage:
#   ./scripts/npm-audit-fix.sh [package_filter] [environment]
#   Example: ./scripts/npm-audit-fix.sh @cisco/analytics dev
#
# For more information, see:
#   https://docs.npmjs.com/cli/v8/commands/npm-audit
#   https://docs.npmjs.com/cli/v8/commands/npm-audit-fix

package_filter="${1:-@cisco/*}"
environment="${2:-prod}"

npx lerna \
    --scope "$package_filter" \
    exec -- npm audit fix --only=${environment} --registry=${NPM_REGISTRY}
