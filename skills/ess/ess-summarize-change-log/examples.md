# Examples

## Before (verbose input)

```
* fix(api-client): centralize deployment naming in deploy CLI

Shell scripts were building deployment names and passing pre-suffixed --name
values, which produced double-encoded names like my-service-prod-dev. ...

* fix(infra): align prod NAT gateway IPs with the prod cluster
...

* fix(api-client): address PR #123 review comments
...

* docs(api-client): port deployment naming docs from #120
...

* fix(api-client,web): address PR #123 review comments
...
```

## After (5 bullets, validated)

See [examples-good.md](examples-good.md) — the canonical fixture `validate-summary.sh` runs against.

Subject lengths (all ≤50):

| Subject | Length |
| --- | --- |
| `fix(api-client): centralize deploy naming` | 41 |
| `fix(infra): pin prod egress to NAT gateway` | 42 |
| `fix(cli): defer delete confirm` | 30 |
| `docs(api-client): document --deployment` | 39 |
| `fix(web): align listener id messaging` | 37 |

## Bad vs good subjects

| Bad (process/meta) | Good (outcome) |
| --- | --- |
| `fix: address PR #123 review comments` | `fix(cli): defer delete confirm` |
| `docs: port deployment naming docs from #120` | `docs(api-client): document --deployment` |
| `chore: follow up on review` | `fix(web): align listener id messaging` |
| `fix: cherry-pick doc improvements` | `docs(api-client): document --deployment` |

## Validate the good example

```bash
scripts/validate-summary.sh \
  examples-good.md
```
