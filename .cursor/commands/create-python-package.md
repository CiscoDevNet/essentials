Create a new Python package using Poetry in the specified directory.

## Parameters

- **directory_location**: The directory path where the new package should be created
- **package_name**: The name of the Python package to create

## Behavior

1. If `directory_location` is not provided, ask the user: "What directory should the package be created in?"
2. If `package_name` is not provided, ask the user: "What should the package be named?"
3. Check the root `pyproject.toml` file for `package-mode = false` in the `[tool.poetry]` section. If the section doesn't exist or `package-mode` is not set to `false`, add or update it:
   ```toml
   [tool.poetry]
   package-mode = false
   ```
   This ensures the root is not packaged up and is only used for dependency management in the mono-repo.
4. Navigate to the specified directory location (create it if it doesn't exist)
5. Run `poetry new <package_name>` in that directory
6. Add the new package to the project's root `pyproject.toml` file in the `[tool.poetry.dependencies]` section (create the section if it doesn't exist)
7. The entry should use the format: `<package_name> = { path = "<relative_path_from_root>/<package_name>", develop = true }`
   - Convert underscores in package_name to hyphens for the dependency name (e.g., `my_new_package` becomes `my-new-package`)
   - The path should be relative to the workspace root (e.g., if directory_location is `tools/python` and package_name is `my_new_package`, the path would be `tools/python/my-new-package`)
8. Confirm the package was created successfully and added to the root pyproject.toml

## Example Usage

**With parameters:**

- directory_location: `tools/python`
- package_name: `my_new_package`
- This will create the package at `tools/python/my-new-package/` and add to root `pyproject.toml`:
  ```toml
  [tool.poetry.dependencies]
  my-new-package = { path = "tools/python/my-new-package", develop = true }
  ```

**Without parameters:**

- Prompt user for directory location
- Prompt user for package name
- Then proceed with creation

## Notes

- The directory location can be absolute or relative to the workspace root
- If the directory doesn't exist, create it before running `poetry new`
- The package name should follow Python naming conventions (lowercase, underscores allowed)
- The dependency name in pyproject.toml should use hyphens (e.g., `my-new-package`) while the package directory name created by `poetry new` will also use hyphens
- If `[tool.poetry.dependencies]` section doesn't exist in the root pyproject.toml, create it before adding the new package
- The root `pyproject.toml` must have `package-mode = false` to indicate it's a mono-repo root used only for dependency management, not for packaging
