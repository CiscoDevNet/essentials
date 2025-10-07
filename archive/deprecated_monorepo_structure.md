# Cisco DevNet Essentials - Monorepo Structure Summary

**Repository Purpose**: A monorepo of packages to help developers build, release, and run great software, focusing on Adaptive Cards, analytics, bot development, and cloud deployment.

## Root-Level Directories

### `.husky/`
**Purpose**: Git hooks management using Husky
**Key Files**: `pre-commit` hook
**Functionality**:
- Runs linting, tests, and security scans before each commit
- Commands: `npm run lint`, `npm test`, `./Taskfile scan`
- Automatically skips in CI environments
- **Migration Note**: Keep for code quality enforcement

### `act/`
**Purpose**: GitHub Actions local testing configurations
**Contents**: JSON configurations for testing GitHub workflows locally
- `pull-request.json`, `version-packages.json`, `push.json`
- `close-automated-pull-request.json`, `complete-version-packages.json`
- **Migration Note**: May need updating for new Turborepo workflows

### `docs/` (Primary Documentation App)
**Purpose**: Main documentation site for the entire monorepo
**Technology**: Docusaurus 2
**Content Structure**:
- `docs/api.md` - API documentation
- `docs/how-to/` - How-to guides (e.g., use-gcloud.md)
- `docs/topics/` - Topic guides (e.g., docker/)
- `docs/tutorials/` - Tutorials (e.g., cisco.md)
- `blog/` - Blog posts and announcements
- **Target Audience**: External users and contributors
- **Migration**: **DEPRECATED** - Documentation sites no longer needed

### `github/`
**Purpose**: Draft GitHub workflows and templates
**Contents**: Template workflows for linting, publishing, testing
- `draft-workflows/lint.yml`, `publish-packages.yml`, etc.
- **Status**: Draft/template workflows (not active)
- **Migration Note**: Review and integrate into `.github/workflows/`

### `scripts/`
**Purpose**: Development and maintenance scripts
**Structure**:
- `docs/make/api/` - API documentation generation
- `lerna/audit-fix.sh` - Lerna-specific utilities
- `sast/gitleaks/` - Security scanning configurations
- `npm-unpublish.sh` - Package management utilities
- **Migration Note**: Will need updating for Turborepo commands

### `templates/`
**Purpose**: Project templates and scaffolding
**Contents**:
- `python_template/` - Complete Python project template
  - Poetry configuration, pre-commit hooks, testing setup
  - Scripts for git configuration, Poetry installation
  - Source code structure and documentation
- **Migration**: Move to `tools/templates/` or keep as `templates/`

## Package Structure

### `packages/cisco/` - Main Package Namespace

#### Bot Development Ecosystem
**Purpose**: Complete bot development framework for Cisco platforms

##### `analytics/` (v0.4.5)
**Purpose**: User event tracking middleware for bots
**Key Features**:
- Event tracking configuration
- Analytics constants and utilities
- Integration with bot middleware

##### `bot-commands/` (v0.4.5)
**Purpose**: Base command handling system for bot intents
**Key Features**:
- Command configuration and constants
- Error handling for controller assignments
- GIF and card integrations
- Help system functionality

##### `bot-factory/` (v0.4.5)
**Purpose**: Bot creation and configuration utilities
**Key Features**:
- Bot instantiation and setup
- Middleware configuration management
- Error handling for bot creation

##### `bot-middleware/` (v0.4.5)
**Purpose**: Middleware for bot message processing
**Key Features**:
- Analytics integration
- Intent processing and configuration
- People management (standard and Webex)
- Client configuration and error handling

##### `cards/` (v0.4.5)
**Purpose**: Adaptive Cards components and utilities
**Key Features**:
- Card constants and configurations
- Adaptive Cards integration

#### Integration Packages
**Purpose**: External service integrations

##### `google/` (v0.4.5)
**Purpose**: Google Cloud authentication and API utilities
**Key Features**:
- Authentication configuration and constants
- Error handling for auth failures
- Google Cloud service integration

##### `salesforce/` (v0.4.5)
**Purpose**: Salesforce API integration and adapters
**Key Features**:
- Direct and Salesforce adapters
- HTTP error handling
- Login/logout management
- Salesforce API wrapper

##### `releases/` (v0.4.5)
**Purpose**: Deployment tools for Google Cloud and OpenShift
**Key Features**:
- Platform naming conventions
- Google Cloud release management
- OpenShift deployment utilities
- Release configuration and testing

#### Utility Packages

##### `core/` (v0.4.5)
**Purpose**: Core utilities and shared functionality
**Key Features**:
- Base utilities used across packages
- Testing infrastructure

##### `docs-docusaurus/` (v0.2.5) - **DEPRECATED**
**Purpose**: Shared Docusaurus configurations and utilities
**Key Features**:
- Docusaurus config and utilities for documentation
- Blog configuration helpers
- Shared documentation patterns
- **Used by**: `digital-garden` package (also deprecated)
- **Migration**: Remove with documentation sites

#### Applications

##### `digital-garden/` (v0.4.5) - **DEPRECATED**
**Purpose**: Personal knowledge management site (Docusaurus)
**Technology**: Docusaurus 2 with React
**Content Structure**:
- `docs/tutorials/git/` - Git tutorials (squash commits, delete branches, create gitignore)
- `docs/tutorials/starter/` - Getting started tutorials
- `docs/snippets/` - Code snippets and quick references
- `blog/` - Personal blog posts and learning notes
- `src/pages/projects/` - Project showcase pages
- **Deployment**: Configured for Netlify
- **Dependencies**: Uses `@cisco/docs-docusaurus`
- **Scope**: Individual developer knowledge base
- **Migration**: **DEPRECATED** - Documentation sites no longer needed

### `packages/gve-google/`
**Purpose**: Google-specific packages (legacy)
**Status**: Appears empty/deprecated
**Migration**: Evaluate for removal

## Configuration Files

### Package Management
- **`package.json`**: Root workspace configuration with Lerna scripts
- **`lerna.json`**: Lerna monorepo configuration (`packages/cisco/*`, `packages/gve/*`, `docs/*`)
- **`package-lock.json`**: Dependency lock file

### Development Tools
- **`Taskfile`**: Custom task runner (35 lines of build/test commands)
- **`.gitignore`**, **`.npmignore`**: Version control and publishing exclusions

### Documentation & Legal
- **`README.md`**: Main repository documentation
- **`LICENSE`**: Apache 2.0 license
- **`CODE_OF_CONDUCT.md`**: Community guidelines

## Dependency Analysis

### Key Dependencies
- **No circular dependencies** found between packages
- **`digital-garden` is completely independent** - nothing depends on it
- **`docs-docusaurus` is used by `digital-garden`** for shared Docusaurus utilities
- **All packages are independently versioned** using Lerna

### Package Relationships
```
docs-docusaurus → (used by) → digital-garden
analytics ← (used by bots) ← bot-middleware
bot-commands ← (used by) ← bot-factory
cards ← (used by) ← bot-commands
core ← (used by) ← multiple packages
```

## Migration Recommendations

### Applications (Deprecated)
1. **`docs/`** → **DEPRECATED** (primary documentation site - no longer needed)
2. **`packages/cisco/digital-garden/`** → **DEPRECATED** (personal knowledge base - no longer needed)

### Libraries (Reorganize in `packages/`)
- **Bot Ecosystem**: Group related bot packages
- **Integrations**: google, salesforce, releases
- **Utilities**: core, ~~docs-docusaurus~~ (deprecated with documentation sites)
- **Consider TypeScript Migration**: Current packages are JavaScript

### Tools/Infrastructure
- **Keep**: `.husky/`, `scripts/`, `templates/`
- **Update**: `Taskfile`, GitHub workflows for Turborepo
- **Replace**: Lerna configs with Turborepo configs
- **Migrate**: From npm to pnpm for better performance

## Technology Stack
- **Languages**: JavaScript (primary), some TypeScript configurations
- **Documentation**: Docusaurus 2
- **Package Manager**: npm (recommend migrating to pnpm)
- **Monorepo Tool**: Lerna (migrating to Turborepo)
- **Testing**: Jest
- **Linting**: ESLint with Prettier
- **Git Hooks**: Husky
- **CI/CD**: GitHub Actions
- **Deployment**: Netlify (for documentation sites)

This structure represents a mature monorepo focused on bot development, cloud deployment, and developer tooling, with clear separation between applications and reusable libraries.
