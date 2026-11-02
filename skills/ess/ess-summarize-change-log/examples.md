# Examples

## Before (verbose input)

```
* fix(langsmith-client): centralize deployment naming in deploy CLI

Shell scripts were building deployment names and passing pre-suffixed --name
values, which produced double-encoded names like hello-agent-prod-dev. ...

* fix(azure-ai): align prod NAT gateway IPs with LangSmith hybrid cluster
...

* fix(langsmith-client): address PR #513 review comments
...

* docs(langsmith-client): port deployment naming docs from #510
...

* fix(langsmith-client,hello-agent): address PR #513 review comments
...
```

## After (5 bullets, validated)

See [examples-good.md](examples-good.md) — the canonical fixture `validate-summary.sh` runs against.

Subject lengths (all ≤50):

| Subject | Length |
| --- | --- |
| `fix(langsmith-client): centralize deploy naming` | 47 |
| `fix(azure-ai): align prod NAT gateway IPs` | 41 |
| `fix(langsmith-client): defer delete confirm` | 43 |
| `docs(langsmith-client): document --deployment` | 45 |
| `fix(hello-agent): align listener id messaging` | 45 |

## Bad vs good subjects

| Bad (process/meta) | Good (outcome) |
| --- | --- |
| `fix: address PR #513 review comments` | `fix(langsmith-client): defer delete confirm` |
| `docs: port deployment naming docs from #510` | `docs(langsmith-client): document --deployment` |
| `chore: follow up on review` | `fix(hello-agent): align listener id messaging` |
| `fix: cherry-pick doc improvements` | `docs(langsmith-client): document --deployment` |

## Validate the good example

```bash
scripts/validate-summary.sh \
  examples-good.md
```
