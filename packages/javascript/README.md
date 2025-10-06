# JavaScript Packages

This directory contains JavaScript/Node.js packages for essential tools and utilities.

## Packages

- **@cisco/analytics** - Analytics events and constants to track system usage
- **@cisco/bot-commands** - Create responsive bot commands with ease
- **@cisco/bot-factory** - Create Webex bots
- **@cisco/bot-middleware** - Middleware to intercept messages
- **@cisco/cards** - Create Adaptive Cards and rich messages
- **@cisco/core** - Helpful functions to reduce parsing and errors
- **@cisco/docs-docusaurus** - Docusaurus config and utilities
- **@cisco/google** - Utilities to work with Google Cloud
- **@cisco/releases** - Release management tools
- **@cisco/salesforce** - Salesforce integration utilities

## Development

### Prerequisites

- Node.js (version specified in `.nvmrc` at the project root)
- npm

### Linting

This project uses ESLint and Prettier to maintain code quality and consistency.

#### Install Dependencies

```bash
cd packages/javascript
npm install
```

#### Run Linting

To check for linting issues:

```bash
# Run both ESLint and Prettier checks
npm run lint

# Run only ESLint
npm run lint:eslint

# Run only Prettier
npm run lint:prettier
```

#### Linting Configuration

- **ESLint**: Configuration in `.eslintrc.json`
  - Extends recommended rules plus import, sonarjs, and prettier configs
  - Supports CommonJS and ES2021
  - Configured for Node.js and Jest environments

- **Prettier**: Configuration in `.prettierrc.json`
  - 2-space indentation
  - Semicolons required
  - 80 character line width

#### GitHub Actions

Linting runs automatically on:
- Pull requests affecting JavaScript files
- Pushes to `main` and `turborepo` branches
- Manual workflow dispatch

The workflow file is located at `.github/workflows/lint.yml`.

## License

[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/)
