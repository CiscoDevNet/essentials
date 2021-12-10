#!/usr/bin/env python3

from pathlib import Path

DEFAULT_CONFIG_FILENAME = ".pre-commit-config.yaml"

DEFAULT_CONFIG = """
repos:
  - repo: local
    hooks:
      - id: default
        name: pre-commit check
        description: Run placeholder pre-commit check as a test
        language: system
        entry: echo
        args:
          - 'Running pre-commit check...'
        files: ''
      - id: test
        name: pytest
        description: Run tests with pytest
        language: system
        entry: pytest
        types:
          - python
  - repo: https://github.com/commitizen-tools/commitizen
    rev: master
    hooks:
      - id: commitizen
        stages: [commit-msg]
"""


def make():
    config_file = Path(DEFAULT_CONFIG_FILENAME)

    if config_file.is_file():
        print(f"{DEFAULT_CONFIG_FILENAME} already exists.")
    else:
        with open(DEFAULT_CONFIG_FILENAME, "w") as new_config_file:
            new_config_file.write(DEFAULT_CONFIG)
        print(f"Wrote {DEFAULT_CONFIG_FILENAME}")


if __name__ == "__main__":
    make()
