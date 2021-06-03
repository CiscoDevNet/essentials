# !/bin/bash
# description: Creates Talisman HTML report
# author: Matt Norris <matnorri@cisco.com>

# Assume Talisman is installed globally.
TALISMAN_HOME="${HOME}/.talisman/bin"
talisman_exe="${TALISMAN_HOME}/talisman_darwin_amd64"

project_root_dir="."
reports_dir="${project_root_dir}/output/reports"

html_dir_name="talisman_html_report"
html_dir="${project_root_dir}/${html_dir_name}"

# Scanning requires a USER, but the user does not need to be valid.
empty_user="_"

USER=${empty_user} ${talisman_exe} \
  --scanWithHtml \
  --ignoreHistory \
  --reportdirectory=${reports_dir}

# https://github.com/jaydeepc/talisman-html-report
# does not respect the Talisman --reportdirectory option.
# Move the generated directory manually.
rsync -aI ${html_dir} ${reports_dir}
rm -fr ${html_dir}

echo "Done."
echo
