---
description: Handle missing environment variables or credentials by sourcing .env files
globs:
alwaysApply: true
---

# Environment Variables and Credentials

When a command fails due to missing environment variables or credentials, such as:

- `passphrase must be set with PULUMI_CONFIG_PASSPHRASE`
- `Missing required environment variable`
- `API key not found`
- `Authentication failed`
- `Credentials not configured`

Do NOT tell the user to run commands in their own terminal.

## Resolution Steps

1. Check if a `.env` file exists in the current project directory
2. Ask the user: "I encountered a credentials/environment variable error. Can I source the `.env` file to get the required values?"
3. If approved, run commands by sourcing the .env first:

```bash
set -a && source .env && set +a && <command>
```

## Security Notes

- Never read or display the contents of `.env` files (they contain secrets)
- Always verify `.env` is gitignored before proceeding
- The `.env` file should contain the required environment variables
