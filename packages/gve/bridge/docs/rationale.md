# Rationale

Monorepos work well in isolation. But if you want develop in more than one simultaneously, they become problematic. The mechanisms they use to `npm link` within a repo directory structure don't work across repos. Manually using `npm link` to connect repos causes problems too.

# Methodology

## Copy

- Copy all packages from a source directory into a target directory.
  - Target directory is relative to the current repo.
  - Assume target (this) repo is a lerna repo.
  - Assume target packages are under `packages`.
  - Place all source packages into a `packages` sub-directory. The sub-directory name is the name of the source directory, i.e., _org_ name. Or, if the source directory name is simply "packages", create a unique target sub-directory name.
  - If an _org_ name is given, use it as the sub-directory in `packages`.

## Include

- Update target repo's `lerna.json` to include the new target sub-directory in `packages`.

## Ignore

- gitignore those packages (target sub-directory) so they will not be committed in this repo.

## Do not publish

- ~~Change each target package's `package.json` to private so it will not be published: https://github.com/lerna/lerna/issues/953~~
- Update `lerna.json` to ignore the packages when publishing.
