# act

Run GitHub Actions locally.

Version packages after merging a PR using [the job flag](https://github.com/nektos/act#example-commands)l

```sh
act -j version-packages --secret-file .env -e act/close-pull-request.json
```

Publish packages to NPM after versioning the packages.

```sh
act -j publish-packages --secret-file .env -e act/complete-version-packages.json
```
