#!/bin/sh

brew install commitizen

# Make the pre-commit-config.yaml file and install it as a hook.
poetry run make-pre-commit-config
poetry run pre-commit install --hook-type commit-msg

# Fix any warnings.
poetry run pre-commit autoupdate
