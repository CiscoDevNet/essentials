# Makefile
# description: Install, build, and run this project.
# author: Matt Norris <matnorri@cisco.com>

init: install hooks

install:
	scripts/install-poetry.sh
	poetry run update-pyproject

gitignore:
	scripts/make-gitignore.sh

hooks:
	scripts/install-hooks.sh

python-version:
	scripts/make-python-version.sh

.PHONY: hooks install
