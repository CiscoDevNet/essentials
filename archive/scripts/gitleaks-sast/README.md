# Gitleaks SAST (Static Application Security Testing)

This directory contains the gitleaks configuration and scripts for scanning the repository for secrets, credentials, and other sensitive information.

## Overview

Gitleaks is a SAST tool for detecting and preventing secrets in git repositories. This setup provides multiple ways to scan for secrets both locally and in CI/CD pipelines.

## Files

### Scripts
- **`scan.sh`** - Main scanning script that runs gitleaks detection
- **`config.toml`** - Active gitleaks configuration with allowlisted commits
- **`example-config.toml`** - Example configuration showing custom rules

### Configuration Files
- **`config.toml`** - Production configuration that allowlists specific commits containing false positives
- **`example-config.toml`** - Template showing how to define custom detection rules

## How It Works

### Entry Points

1. **Taskfile Integration** (`./Taskfile`)
   ```bash
   ./Taskfile scan          # Runs gitleaks scan (default task)
   ./Taskfile scan:action   # Runs GitHub Actions gitleaks locally
   ./Taskfile protect       # ⚠️  BROKEN: References non-existent protect.sh
   ```

2. **NPM Scripts** (`package.json`)
   ```bash
   npm run secrets:scan     # Runs scripts/gitleaks-sast/scan.sh
   ```

3. **Git Hooks** (`.husky/pre-commit`)
   - Automatically runs `./Taskfile scan` before each commit
   - Prevents commits if secrets are detected

4. **GitHub Actions** (`.github/workflows/scan-leaks.yml`)
   - Runs on pull requests using the official gitleaks action
   - Independent of local scripts

### Workflow Integration

#### Development Workflow
1. **Pre-commit**: When you commit, husky runs `./Taskfile scan` → calls `scripts/gitleaks-sast/scan.sh` → runs gitleaks with config
2. **Manual scanning**: Run `./Taskfile scan` or `npm run secrets:scan` anytime
3. **Local CI testing**: Use `./Taskfile scan:action` to test GitHub Actions locally

#### CI/CD Workflow
- **Pull Requests**: GitHub Actions automatically runs gitleaks scan using the official action
- **Independent verification**: CI runs separately from local scripts for additional security

## Configuration

### Active Configuration (`config.toml`)
```toml
[allowlist]
    description="Allow constants referring to Private Key's standard prefix and suffix"
    commits=["cd185337daa5f2651d5d8e21eebad673de5c7f5d", "92ad1347fb9b77f8813aeb519b09557671842646"]
```

This configuration allowlists specific commits that contain false positives (like constants with "Private Key" text that aren't actual secrets).

### Custom Rules (`example-config.toml`)
Shows how to define custom detection patterns:
```toml
[[rules]]
  description = "password text"
  regex = '''password'''
  tags = ["password"]
```

## Usage

### Quick Start
```bash
# Scan for secrets (most common)
./Taskfile scan

# Or using npm
npm run secrets:scan

# Test GitHub Actions locally
./Taskfile scan:action
```

### Manual Execution
```bash
# Direct script execution
./scripts/gitleaks-sast/scan.sh

# Direct gitleaks command
gitleaks detect --config=scripts/gitleaks-sast/config.toml --verbose
```

## Security Features

1. **Pre-commit Prevention**: Stops commits containing secrets before they reach the repository
2. **CI/CD Verification**: Double-checks in GitHub Actions for additional security
3. **Configurable Rules**: Customize detection patterns for your specific needs
4. **Allowlist Support**: Handle false positives by allowlisting specific commits

## Known Issues

1. **⚠️  BROKEN: Missing protect.sh**: The Taskfile references `scripts/gitleaks-sast/protect.sh` but this file doesn't exist
   - Running `./Taskfile protect` will fail
   - This function needs to be implemented or removed from the Taskfile

2. **Unused get-commit-date.sh**: The `scripts/git-get-commit-date.sh` utility isn't currently used by any gitleaks functionality


## References

- [Gitleaks Documentation](https://github.com/zricethezav/gitleaks)
- [Gitleaks GitHub Action](https://github.com/zricethezav/gitleaks-action)
- [Configuration Examples](https://github.com/zricethezav/gitleaks#configuration)

## Author

Matt Norris <matnorri@cisco.com>
