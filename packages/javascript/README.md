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

### Testing

This project uses Jest for testing. Several packages include test files:
- `@cisco/releases` - Release management tests
- `@cisco/core` - Core utility function tests
- `@cisco/docs-docusaurus` - Docusaurus config tests
- `@cisco/bot-commands` - Bot command tests
- `@cisco/salesforce` - Salesforce integration tests

#### Install Dependencies

```bash
cd packages/javascript
npm install
```

#### Run Tests

To run all tests:

```bash
# Run all tests across all packages
npm test
```

To test a specific package:

```bash
# Navigate to the package directory
cd cisco/releases
npm test
```

### Linting

This project uses ESLint and Prettier to maintain code quality and consistency.

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

Both linting and testing run automatically on:
- Pull requests affecting JavaScript files
- Manual workflow dispatch

The workflow files are:
- `.github/workflows/lint.yml` - Linting
- `.github/workflows/test.yml` - Testing

## License

[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/)
