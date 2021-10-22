# !/bin/bash
# description: Scan current branch for secrets
# author: Matt Norris <matnorri@cisco.com>

project_dir="."
scripts_dir="scripts/secrets"

# Get the current branch.
# https://stackoverflow.com/a/12142066/154065
current_branch=`git rev-parse --abbrev-ref HEAD`

commit_date=`${scripts_dir}/get-commit-date.sh ${current_branch}`

echo "First commit of current branch '${current_branch}': ${commit_date}"
echo "Scanning current branch '${current_branch}' for secrets..."
echo

# TODO: commit-since flag doesn't work.
# --commit-since=${commit_date} \

gitleaks \
    --append-repo-config \
    --branch=${current_branch} \
    --path=${project_dir} \
    --repo-config-path="${scripts_dir}/config.toml" \
    --verbose
