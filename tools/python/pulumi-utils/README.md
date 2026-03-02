# Pulumi Utils

Common utilities for Pulumi projects to promote code reuse and consistency across infrastructure deployments.

## Overview

This package provides helper functions and utilities that are commonly needed across multiple Pulumi projects, including:

- Resource naming conventions with stack-based suffixing
- Configuration management
- Custom error types

## Installation

### Using Poetry (recommended)

Add to your `pyproject.toml`:

```toml
dependencies = [
    "pulumi-utils",
]
```

Then install:

```bash
poetry add pulumi-utils
```

### Using pip

```bash
pip install pulumi-utils
```

## Usage

### Resource Naming

The naming utilities help create consistent resource names across your infrastructure:

```python
import pulumi
from pulumi_utils import get_resource_name, get_suffix

# Get the stack-based suffix
suffix = get_suffix()
# Returns: 'dev' for dev stack, '' for prod stack, 'staging' for staging stack

# Generate a resource name
resource_name = get_resource_name("myapp", "postgres", "server")
# In dev stack: 'myapp-postgres-server-dev'
# In prod stack: 'myapp-postgres-server'

# Use a custom separator (e.g., for database names)
db_name = get_resource_name("myapp", "db", separator="_")
# In dev stack: 'myapp_db_dev'

# Use for storage accounts (no separator)
storage_name = get_resource_name("myapp", "storage", separator="")
# In dev stack: 'myappstorage'  (then format with Azure utils)
```

### Complete Pulumi Example

```python
import pulumi
import pulumi_azure_native as azure_native
from pulumi_utils import get_resource_name

config = pulumi.Config()
project_name = pulumi.get_project()

# Create resource group with consistent naming
resource_group_name = config.get("resourceGroupName") or get_resource_name(
    project_name, "rg"
)

resource_group = azure_native.resources.ResourceGroup(
    "resource-group",
    resource_group_name=resource_group_name,
    location="eastus",
)

# Create storage account with consistent naming
storage_name = config.get("storageAccountName") or get_resource_name(
    project_name, "storage", separator=""
)

# Note: Azure storage names need additional formatting (lowercase, no dashes)
# Use azure-utils package for Azure-specific name formatting
```

## API Reference

### Naming Functions

#### `get_suffix() -> str`

Get the suffix for resources based on the current stack name.

**Returns:**

- Empty string if stack name starts with "prod"
- Stack name for all other stacks

**Examples:**

```python
# In dev stack
get_suffix()  # Returns: 'dev'

# In prod stack
get_suffix()  # Returns: ''

# In staging stack
get_suffix()  # Returns: 'staging'
```

#### `get_resource_name(*parts: str, separator: str = "-") -> str`

Generate a resource name by joining parts and appending the stack suffix.

**Parameters:**

- `*parts`: Variable number of string parts to join
- `separator`: String to use between parts (default: "-")

**Returns:**

- Formatted resource name with stack suffix

**Examples:**

```python
# Basic usage
get_resource_name("myapp", "db")
# Returns: 'myapp-db-dev' (in dev stack)

# Custom separator
get_resource_name("myapp", "db", separator="_")
# Returns: 'myapp_db_dev' (in dev stack)

# Multiple parts
get_resource_name("myapp", "postgres", "primary", "server")
# Returns: 'myapp-postgres-primary-server-dev' (in dev stack)
```

### Configuration Constants

#### `DEFAULT_SEPARATOR`

Default separator used in resource names: `"-"`

### Custom Exceptions

#### `PulumiUtilsError`

Base exception for all pulumi_utils errors.

#### `InvalidStackName`

Raised when a stack name is invalid.

**Attributes:**

- `stack_name`: The invalid stack name
- `reason`: Why the stack name is invalid

#### `InvalidResourceName`

Raised when a resource name is invalid.

**Attributes:**

- `name`: The invalid resource name
- `reason`: Why the resource name is invalid

## Stack Naming Convention

This package follows a convention for stack names:

- **Production stacks**: Start with "prod" (e.g., "prod", "production")

  - No suffix is added to resource names
  - Example: `myapp-postgres-server`

- **Non-production stacks**: Any other name (e.g., "dev", "staging", "test")
  - Stack name is added as a suffix
  - Example: `myapp-postgres-server-dev`

This convention helps:

- Keep production resource names clean and predictable
- Clearly identify non-production resources
- Prevent naming conflicts across environments

## Integration with Other Packages

### With azure-utils

Combine `pulumi-utils` with `azure-utils` for Azure-specific formatting:

```python
from pulumi_utils import get_resource_name
from azure_utils import format_storage_account_name

# Generate name with Pulumi utils
raw_storage_name = get_resource_name("myapp", "storage", separator="")

# Format for Azure requirements (3-24 chars, lowercase, no dashes)
storage_name = format_storage_account_name(raw_storage_name)
```

## Development

### Setup

```bash
# Clone the repository
cd tools/python/pulumi-utils

# Install dependencies
poetry install
```

### Testing

```bash
# Run tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=pulumi_utils
```

### Building

```bash
# Build the package
poetry build
```

## Best Practices

1. **Consistent Naming**: Always use `get_resource_name()` for resource names to ensure consistency across your infrastructure.

2. **Stack Convention**: Follow the "prod" prefix convention for production stacks to benefit from automatic suffix behavior.

3. **Separator Choice**:

   - Use default "-" for most resources
   - Use "\_" for database names and SQL identifiers
   - Use "" (empty) for storage accounts, then apply Azure-specific formatting

4. **Configuration**: Allow resource names to be overridden via Pulumi config:
   ```python
   name = config.get("resourceName") or get_resource_name("default", "name")
   ```

## Related Packages

- **azure-utils**: Azure-specific utilities for resource name formatting
- **azure-postgres**: Pulumi project for Azure PostgreSQL with examples
- **azure-ai**: Pulumi project for Azure OpenAI with examples

## Contributing

Contributions are welcome! Please ensure:

- All tests pass
- Code follows project style guidelines
- Documentation is updated for new features

## License

MIT

## Author

Matt Norris (matt@mattnorris.dev)
