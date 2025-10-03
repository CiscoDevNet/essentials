#!/bin/sh

# description: Configure git to fetch updates from the template repo.
# author: Matt Norris <matnorri@cisco.com>
# Reference: https://medium.com/@smrgrace/having-a-git-repo-that-is-a-template-for-new-projects-148079b7f178

# Allow this repo to get updates from the template repo,
# but prevent its own code from being pushed to that repo.
git remote rename origin upstream
git remote set-url --push upstream push_disabled
