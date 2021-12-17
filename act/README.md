# act

Run GitHub Actions locally.

Version packages after merging a PR.

```sh
act pull_request --secret-file .env -e act/pull-request.json
```

Publish packages to NPM after versioning the packages.

```sh
act workflow_run --secret-file .env -e act/version-packages-success.json
```
