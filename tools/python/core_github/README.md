# core_github

List and filter GitHub pull requests from the command line.

```bash
prs --state open --output-format json
```

```json
[
  {
    "number": 1137,
    "title": "fix: Compare min(ORDER_NUMBER) between SAVM_NAME and ACCOUNT_NAME",
    "author": { "login": "jack-shih-meraki" },
    "state": "OPEN",
    "mergeStateStatus": "CLEAN",
    "url": "https://github.com/Cisco-DES/aide/pull/1137"
  }
]
```

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-packages
```

Create a `.env` file with your GitHub token:

```
GH_TOKEN=<your-github-personal-access-token>
LOG_LEVEL=INFO
```

The `prs` command also requires the [GitHub CLI](https://cli.github.com/) (`gh`) to be installed and authenticated.

## Usage

### `prs`

The main entry point. Defaults to listing PRs for `Cisco-DES/aide` as JSON.

```bash
prs                                    # all PRs, JSON output
prs --state open                       # open PRs only
prs --author alice --author bob        # filter by author(s)
prs --is-mergeable true --limit 10     # mergeable PRs, max 10
prs --output-format table              # pandas table output
prs --output-format csv > prs.csv      # redirect CSV to file
```

#### Options

| Option             | Type                                  | Default           | Description                                |
| ------------------ | ------------------------------------- | ----------------- | ------------------------------------------ |
| `--org-repo`       | `str`                                 | `Cisco-DES/aide`  | Repository in `org/repo` format            |
| `--author`         | `str` (repeatable)                    |                   | Filter by PR author(s)                     |
| `--state`          | `all` \| `open` \| `closed` \| `merged` | `all`          | PR state filter                            |
| `--limit`          | `int`                                 | 30 (gh default)   | Max PRs to return                          |
| `--draft-status`   | `true` \| `false` \| `both`          |                   | Draft filter                               |
| `--is-mergeable`   | `true` \| `false` \| `both`          |                   | Mergeable filter (`CLEAN` vs `DIRTY`/`UNSTABLE`) |
| `--output-format`  | `json` \| `csv` \| `table`           | `json`            | Output format                              |

### Python API

`GitHubCore` uses the PyGitHub library to search for PRs across all repos you have access to:

```python
from core_github.github_api import GitHubCore

gh = GitHubCore(token="...")
for pr in gh.get_prs():
    print(pr.title, pr.html_url)
```

`get_prs()` in `github_cli` wraps the `gh` CLI for repo-scoped queries with richer filtering:

```python
from core_github.github_cli import get_prs

prs = get_prs(org_repo="Cisco-DES/aide", authors=["mattnorris"], state="open")
```

## Running Tests

```bash
pytest
```

Uses [pytest](https://docs.pytest.org/). No tests have been written yet.

## License

Apache 2.0. See [LICENSE](../../LICENSE).
