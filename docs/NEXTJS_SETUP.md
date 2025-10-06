# Next.js ESLint Configuration

This document describes the Next.js ESLint plugin that was removed from the JavaScript packages configuration, and how to restore it when adding a Next.js application.

## What Was Removed

The Next.js ESLint plugin was removed because the current packages are Node.js libraries/packages, not Next.js applications. The plugin requires a `pages/` or `src/pages/` directory for Next.js routing, which doesn't exist in library packages.

### Removed from `package.json`

```json
"devDependencies": {
  "@next/eslint-plugin-next": "^12.1.6"
}
```

### Removed from `.eslintrc.json`

```json
"extends": [
  "plugin:@next/next/recommended"
]
```

## Why It Was Removed

- The `@next/next` ESLint plugin is specifically for Next.js React applications
- It includes rules like `no-html-link-for-pages` that check for proper Link usage in Next.js
- These rules require a Next.js pages directory structure
- Without a Next.js app, the plugin generates errors like:
  ```
  Pages directory cannot be found at .../pages or .../src/pages
  ```

## How to Restore for Next.js Apps

When you add a Next.js application to this directory, follow these steps:

### 1. Install the Next.js ESLint Plugin

```bash
cd packages/javascript
npm install --save-dev @next/eslint-plugin-next
```

Or use a specific version:

```bash
npm install --save-dev @next/eslint-plugin-next@^12.1.6
```

### 2. Update `.eslintrc.json`

Add the Next.js plugin back to the extends array:

```json
{
  "extends": [
    "eslint:recommended",
    "plugin:import/errors",
    "plugin:import/warnings",
    "plugin:sonarjs/recommended",
    "prettier",
    "plugin:@next/next/recommended"
  ]
}
```

### 3. Next.js-Specific Configuration

If you need to customize the Next.js ESLint rules, you can add them to the rules section:

```json
{
  "rules": {
    "@next/next/no-html-link-for-pages": ["error", "path/to/your/pages/"],
    "@next/next/no-img-element": "error",
    "@next/next/no-page-custom-font": "warn"
  }
}
```

### 4. Consider Separate ESLint Configs

For a monorepo with both Node.js packages and Next.js apps, consider:

**Option A: Separate Config Files**
- Keep the current `.eslintrc.json` for Node.js packages
- Create a separate `.eslintrc.json` in your Next.js app directory with the Next.js plugin

**Option B: ESLint Overrides**
Use overrides in the main `.eslintrc.json`:

```json
{
  "extends": [
    "eslint:recommended",
    "plugin:import/errors",
    "plugin:import/warnings",
    "plugin:sonarjs/recommended",
    "prettier"
  ],
  "overrides": [
    {
      "files": ["nextjs-app/**/*.{js,jsx,ts,tsx}"],
      "extends": ["plugin:@next/next/recommended"]
    }
  ]
}
```

## Next.js ESLint Rules

The `@next/next/recommended` config includes rules for:

- **Link usage**: Ensures proper use of Next.js `<Link>` components
- **Image optimization**: Enforces use of `next/image` instead of `<img>`
- **Font optimization**: Checks for proper font loading
- **Script optimization**: Validates `next/script` usage
- **Document structure**: Ensures proper `_document.js` setup
- **Head component**: Validates Next.js `<Head>` usage

## Additional Resources

- [Next.js ESLint Documentation](https://nextjs.org/docs/basic-features/eslint)
- [Next.js ESLint Plugin on npm](https://www.npmjs.com/package/@next/eslint-plugin-next)
- [Next.js ESLint Config](https://nextjs.org/docs/app/building-your-application/configuring/eslint)

## Date Removed

- **Date**: October 6, 2025
- **Reason**: No Next.js applications in current package structure
- **Affected Files**: `package.json`, `.eslintrc.json`
