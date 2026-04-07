# CIDR Entry Points

The EKS API server allowlist is built from three sources, merged and
deduplicated at deploy time:

```python
_all_cidrs = list(
    dict.fromkeys(
        get_cidrs(LANGSMITH)          # 1. Built-in LangSmith IPs
        + tuple(_org_cidrs)           # 2. Entry point plugins
        + cfg.extra_public_access_cidrs  # 3. Manual overrides
    )
)
```

Source 2 uses [Python entry points](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/#using-package-metadata),
the PyPA-standard plugin discovery mechanism (`importlib.metadata`). Any
installed package can provide CIDRs by declaring an entry point in the
`langsmith_hosting.cidrs` group.

## How it works

### Consumer side (langsmith-hosting)

`__main__.py` discovers all registered CIDR providers at runtime:

```python
from importlib.metadata import entry_points

_org_cidrs: list[str] = []
for _ep in entry_points(group="langsmith_hosting.cidrs"):
    _org_cidrs.extend(_ep.load())
```

`entry_points(group=...)` scans every installed package's metadata for
entries in that group. `ep.load()` performs the import and attribute
lookup, returning the CIDR tuple.

### Provider side (any package)

A provider declares entry points in its `pyproject.toml`:

```toml
[project.entry-points."langsmith_hosting.cidrs"]
my-corp = "my_network.corporate:CORPORATE_CIDRS"
```

Each entry follows the format `name = "module.path:ATTRIBUTE"`:

| Part | Meaning |
| --- | --- |
| `my-corp` | Human-readable name (used for inspection, not code) |
| `my_network.corporate` | Python module to import |
| `CORPORATE_CIDRS` | Attribute on that module — must be an iterable of CIDR strings |

### Concrete example

An internal networking package could declare:

```toml
[project.entry-points."langsmith_hosting.cidrs"]
corporate = "my_network.corporate:CORPORATE_CIDRS"
```

When that package is installed (e.g., via `uv sync --all-packages`), its
CIDRs are automatically discovered and included. When it is absent,
`entry_points()` returns nothing and only the LangSmith IPs + manual
overrides are used.

## Inspecting registered entry points

```bash
uv run python -c "
from importlib.metadata import entry_points
for ep in entry_points(group='langsmith_hosting.cidrs'):
    print(f'{ep.name}: {ep.load()}')
"
```

## Adding a new CIDR provider

1. Create a Python package with a module that exports a tuple of CIDR
   strings (e.g., `my_network/firewalls.py` with `SCANNER_IPS`).
2. Add the entry point to the package's `pyproject.toml`:

   ```toml
   [project.entry-points."langsmith_hosting.cidrs"]
   scanner = "my_network.firewalls:SCANNER_IPS"
   ```

3. Install the package in the same environment as `langsmith-hosting`
   (or add it to the uv workspace).
4. Run `uv sync --all-packages` to register the entry point.
5. `pulumi preview` will now include the new CIDRs.
