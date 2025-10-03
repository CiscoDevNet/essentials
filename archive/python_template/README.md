# Commitizen

## Install

```sh
brew install commitizen
poetry run cz init
```

## Commit

```sh
poetry run cz c
```

# pre-commit

## Install

```sh
poetry run pre-commit-config
poetry run pre-commit install --hook-type commit-msg
```

You may see this warning:

```
[WARNING] The 'rev' field of repo '[https://github.com/commitizen-tools/commitizen](https://github.com/commitizen-tools/commitizen)' appears to be a mutable reference (moving tag / branch). Mutable references are never updated after first install and are not supported. See [https://pre-commit.com/#using-the-latest-version-for-a-repository](https://pre-commit.com/#using-the-latest-version-for-a-repository) for more details. Hint: `pre-commit autoupdate` often fixes this.
```

Fix the warning.

```sh
poetry run pre-commit autoupdate
```

## Run

Run all the pre-commit scripts, even if not committing.

```sh
poetry run pre-commit run --all-files
```

# Poetry

Run Python script with arguments (instead of a Poetry script). See https://stackoverflow.com/a/69406057/154065.

```sh
poetry run python myscript.py my args
```
