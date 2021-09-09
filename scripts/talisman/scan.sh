# !/bin/bash
# description: Creates Talisman HTML report
# author: Matt Norris <matnorri@cisco.com>

# Assume Talisman is installed globally.
talisman_exe="${TALISMAN_HOME}/talisman_darwin_amd64"

reports_dir="./output/reports"
mkdir -p ${reports_dir}

html_dir_name="talisman_html_report"
temp_html_dir="./${html_dir_name}"

${talisman_exe} \
  --scanWithHtml \
  --ignoreHistory \
  --reportdirectory=${reports_dir}

# https://github.com/jaydeepc/talisman-html-report
# does not respect the Talisman --reportdirectory option.
# Move the generated directory manually.
rsync -aI ${temp_html_dir} ${reports_dir}
rm -fr ${temp_html_dir}

echo "Done."
echo
