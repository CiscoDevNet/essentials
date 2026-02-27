Create a new Python package using uv in the specified directory.

## Parameters

- **directory_location**: The directory path where the new package should be created
- **package_name**: The name of the Python package to create

## Behavior

1. If `directory_location` is not provided, ask the user: "What directory should the package be created in?"
2. If `package_name` is not provided, ask the user: "What should the package be named?"
3. Navigate to the specified directory location (create it if it doesn't exist)
4. Run `uv init --lib <package_name>` in that directory
5. Add the new package to the project's root `pyproject.toml` file in the `[tool.uv.workspace]` members list (create the section if it doesn't exist)
6. The entry should use the format: `"<relative_path_from_root>/<package_name>"`
   - Convert underscores in package_name to hyphens for the directory name (e.g., `my_new_package` becomes `my-new-package`)
   - The path should be relative to the workspace root (e.g., if directory_location is `tools/python` and package_name is `my_new_package`, the path would be `tools/python/my-new-package`)
7. Ensure the new package uses hatchling as the build backend:
   ```toml
   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"
   ```
8. Confirm the package was created successfully and added to the root pyproject.toml

## Example Usage

**With parameters:**

- directory_location: `tools/python`
- package_name: `my_new_package`
- This will create the package at `tools/python/my-new-package/` and add to root `pyproject.toml`:
  ```toml
  [tool.uv.workspace]
  members = [
      "tools/python/core_github",
      "tools/python/gcp_gemini",
      "tools/python/my-new-package",
  ]
  ```

**Without parameters:**

- Prompt user for directory location
- Prompt user for package name
- Then proceed with creation

## Notes

- The directory location can be absolute or relative to the workspace root
- If the directory doesn't exist, create it before running `uv init`
- The package name should follow Python naming conventions (lowercase, underscores allowed)
- The directory name in the workspace members list should use hyphens (e.g., `my-new-package`)
- If `[tool.uv.workspace]` section doesn't exist in the root pyproject.toml, create it before adding the new package
