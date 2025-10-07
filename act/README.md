This directory contains configuration files and documentation for running local GitHub Actions workflows using the `act` tool.

Scan the repository for secrets and sensitive information with gitleaks.

```sh
act workflow_dispatch -e act/scan-leaks.json
```