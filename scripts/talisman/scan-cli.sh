# !/bin/bash
# description: Gets checksum for all change log files.
# author: Matt Norris <matnorri@cisco.com>
# see: https://stackoverflow.com/questions/4321456/find-exec-a-shell-function-in-linux

get_checksum() {
    "${TALISMAN_HOME}/talisman_darwin_amd64" --checksum=$1 | grep "filename\|checksum"
}

export -f get_checksum

echo fileignoreconfig:
find packages -type f \( -iname "CHANGELOG.md" ! -path "**/node_modules/*" \) \
    -exec bash -c 'get_checksum "$0"' {} \;
echo
