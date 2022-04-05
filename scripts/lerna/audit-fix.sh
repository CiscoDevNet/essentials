# !/bin/bash
# description: Audit the packages matching the given filter
# author: Matt Norris <matnorri@cisco.com>

package_filter="${1:-@cisco/*}"
environment="${2:-prod}"

npx lerna \
    --scope "$package_filter" \
    exec -- npm audit fix --only=${environment} --registry=${NPM_REGISTRY}
