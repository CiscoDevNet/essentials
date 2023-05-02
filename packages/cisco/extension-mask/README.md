## Install

```sh
nvm use
npm ci
```

## Develop

### Build

```sh
npm run build
```

Built files are in the `dist` directory.

### Install directory in Firefox

1. Open Firefox.
2. Type `about:debugging#/runtime/this-firefox` in the address bar, then press Enter.
3. Click on "Load Temporary Add-on..." in the upper right corner.
4. Navigate to the `dist` directory and select the `manifest.json` file.

## Distribute

### Build XPI file

```sh
npm run build:ext
```

Built XPI file is in the `output` directory.

### Install XPI file in Firefox

Install the extension in Firefox by following these steps:

1. Open Firefox.
2. Type `about:addons` in the address bar, then press Enter.
3. Click on the gear icon in the upper right corner and select "Install Add-on From File."
4. Locate the XPI file and click "Open." The extension will be installed in Firefox.
