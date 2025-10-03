# !/bin/bash

# Description: Get the date of the latest commit
# Author: Matt Norris <matnorri@cisco.com>
#
# This script gets the date of the latest commit for a given branch.
#
# Usage:
#   ./scripts/get-commit-date.sh [branch]
#
# By default, it uses the main branch.
#
# For more information, see:
#   https://stackoverflow.com/q/18407526/154065
#   https://stackoverflow.com/a/2514279/154065


branch="${1:-main}"

# Get the given branch's first commit date.
# https://stackoverflow.com/q/18407526/154065
get_first_commit_date() {
    branch="${1:-main}"
    line=`git reflog | grep checkout | grep ${branch} | tail -1`
    line_parts=($line)
    commit=${line_parts[0]}
    echo `get_latest_commit_date ${commit}`
}

# Get the given branch's latest commit date.
# https://stackoverflow.com/a/2514279/154065
get_latest_commit_date () {
    branch="${1:-main}"
    echo `git log -1 --pretty="format:%ci" ${branch}`
}

date=`get_first_commit_date ${branch}`

# Format the date like '2021-01-01'.
# https://stackoverflow.com/a/13402368/154065
date_parts=($date)
formatted_date=${date_parts[0]}

echo ${formatted_date}
