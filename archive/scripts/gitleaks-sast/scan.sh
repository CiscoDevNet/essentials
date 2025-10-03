# !/bin/bash

# Description: Scan current branch for secrets
# Author: Matt Norris <matnorri@cisco.com>
#
# This script scans the current branch for secrets using gitleaks.
#
# Usage:
#   ./scripts/gitleaks-sast/scan.sh
#
# For more information, see:
#   https://github.com/zricethezav/gitleaks

scripts_dir="scripts/gitleaks-sast"

gitleaks detect \
    --config="${scripts_dir}/config.toml" \
    --verbose
