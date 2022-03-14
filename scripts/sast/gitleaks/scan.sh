# !/bin/bash
# description: Scan current branch for secrets
# author: Matt Norris <matnorri@cisco.com>

scripts_dir="scripts/sast/gitleaks"

gitleaks detect \
    --config="${scripts_dir}/config.toml" \
    --verbose
