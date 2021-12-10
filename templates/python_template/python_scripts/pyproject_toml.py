#!/usr/bin/env python3

import argparse
import os
import shutil
import tempfile
import toml

from pathlib import Path

ORIGINAL_PACKAGE_NAME = "python_template"
PYPROJECT_TOML = "pyproject.toml"
PYPROJECT_TOML_PATH = Path(PYPROJECT_TOML)
PROJECT_DIR_NAME = PYPROJECT_TOML_PATH.resolve().parent.name

parser = argparse.ArgumentParser()
parser.add_argument("name", help="the new project name", default=PROJECT_DIR_NAME)


def mkdirp(dir_path):
    """
    Idempotently makes a directory, like `mkdir -p`
    """
    try:
        os.mkdir(dir_path)
    except FileExistsError:
        pass


def create_backup():
    """
    Creates a backup of the current pyproject.toml file.
    """
    BACKUP_DIR_PATH = f"{PYPROJECT_TOML}.bak"
    mkdirp(BACKUP_DIR_PATH)

    BACKUP_FILE_PATH = tempfile.mkstemp(
        prefix="pyproject.", suffix=".toml.bak", dir=BACKUP_DIR_PATH
    )[-1]

    try:
        shutil.copy(PYPROJECT_TOML, BACKUP_FILE_PATH)
    except Exception as e:
        # Clean up by deleting the unused backup file.
        Path(BACKUP_FILE_PATH).unlink()
        raise e

    return BACKUP_FILE_PATH


def update_package_name(name):
    """
    Updates the package name in the directory structure.
    """
    PACKAGE_DIR = Path("./src")
    package = PACKAGE_DIR / ORIGINAL_PACKAGE_NAME
    updated_package = PACKAGE_DIR / name
    os.rename(package, updated_package)

    return updated_package


def update_pyproject_toml(name):
    """
    Creates a backup of the current pyproject.toml, then
    updates the package name in pyproject.toml.
    """
    create_backup()
    parsed_toml = toml.load(PYPROJECT_TOML_PATH)
    parsed_toml["tool"]["poetry"]["name"] = name
    with open(PYPROJECT_TOML_PATH, "w") as updated_file:
        toml.dump(parsed_toml, updated_file)

    return PYPROJECT_TOML_PATH


def update(name=PROJECT_DIR_NAME):
    """
    Updates the package name in the directory structure and pyproject.toml.
    """
    update_package_name(name)
    update_pyproject_toml(name)


if __name__ == "__main__":
    args = parser.parse_args()
    update(args.name)
