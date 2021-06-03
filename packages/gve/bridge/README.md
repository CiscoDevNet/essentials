# Bridge

"Bridge" two or more [Lerna](https://github.com/lerna/lerna) monorepos so that you can develop in all of them simultaneously.

## Installation

Install with [npm](https://www.npmjs.com/).

```bash
npm i -D @gve/bridge
```

## Usage

Point the bridge at the path of the source code you want to use. For example, the `packages` directory of another monorepo.

```bash
export SOURCE_DIR="~/path/to/other/monorepo/packages"
npx bridge ${SOURCE_DIR}
```

`bridge` will:

- Copy the packages into a sub-directory of the current monorepo.
- Update `.gitignore` to ignore them when committing.
- Update `lerna.json` to ignore them when publishing packages.

## Rationale

[Read the rationale](docs/rationale.md) for this approach.

## License

[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/)
