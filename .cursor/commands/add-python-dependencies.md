Add helpful Python dependencies to the current uv project.

## Parameters

- **package_dir**: The directory path where the Python package's `pyproject.toml` file is located

## Behavior

1. If `package_dir` is not provided, check for a `pyproject.toml` file in the current directory. If no `pyproject.toml` is found, ask the user: "What is the package directory location?"
2. Navigate to the package directory (use current directory if `pyproject.toml` exists there, otherwise use the provided or asked-for directory)
3. Add regular dependencies:

   - `python-dotenv` - For loading environment variables from .env files
   - `python-decouple` - For managing settings and configuration

4. Add development dependencies:
   - `black` - Code formatter
   - `pre-commit` - Git hooks framework
   - `pylint` - Linter for Python code
   - `perflint` - Performance linter
   - `ruff` - Fast Python linter and formatter
   - `bandit` - Security linter for Python
   - `pytest` - Testing framework
   - `detect-secrets` - Tool to detect secrets in code

## Commands

Run these commands in the package directory (where `pyproject.toml` exists):

```sh
uv add python-dotenv python-decouple
```

```sh
uv add --group dev black pre-commit pylint perflint ruff bandit pytest detect-secrets
```

## Example Usage

**With parameter:**

- package_dir: `tools/python/my_package`
- This will navigate to `tools/python/my_package/` and run the uv add commands there

**Without parameter:**

- Check current directory for `pyproject.toml`
- If found, use current directory
- If not found, prompt user for package directory location
- Then proceed with adding dependencies

## Notes

- The package directory must contain a `pyproject.toml` file
- The directory location can be absolute or relative to the workspace root
- The dev dependencies will be added to the `[dependency-groups]` dev section in `pyproject.toml`
- Regular dependencies will be added to the `[project]` dependencies section
