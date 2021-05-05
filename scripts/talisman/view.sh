# !/bin/bash
# description: Runs a server to view a Talisman HTML report
# author: Matt Norris <matnorri@cisco.com>

project_root_dir="."
reports_dir="${project_root_dir}/output/reports"

html_dir_name="talisman_html_report"

python -m http.server 9999 -d "${reports_dir}/${html_dir_name}"
