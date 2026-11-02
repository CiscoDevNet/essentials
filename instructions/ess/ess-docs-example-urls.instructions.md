---
description: >-
  Use example.com, example.net, example.org, or example.edu, or a subdomain of
  one, for every illustrative host, URL, and email in code, tests, comments,
  and docs.
applyTo: "**"
---

# Example URLs

Placeholder hosts, URLs, and email addresses use one of four reserved domains, or a
subdomain of one: `example.com`, `example.net`, `example.org`, or `example.edu`. RFC 2606
reserves the first three, and IANA holds all four. Each serves a page that reads: "This
domain is for use in documentation examples without needing permission."

| Placeholder for | Use | Not |
| --------------- | --- | --- |
| A remote host | `host.example.com` | `host.com`, `myhost` |
| An identity provider | `idp.example.com` | `login.vendor.com` |
| A deployed app | `app.example.com` | `my-app.awsapprunner.com` |
| A person | `ada@example.com` | an address at `x.com` or a real company |
| A second organization | `corp.example.net` | `corp.example`, `example.invalid` |

- **Default to `example.com`.** Use `example.net`, `example.org`, or `example.edu` when an
  example needs organizations that are visibly distinct.
- **Only these four.** Other `example.<tld>` names, such as `example.io` or `example.dev`,
  are ordinary domains someone can register. The reserved TLDs `.example`, `.invalid`, and
  `.test` are safe but off-convention: a short fixed list keeps placeholders searchable,
  and secret and PII scanners can allow exactly that list.
- **Real endpoints stay real.** A host the code actually calls (`github.com`,
  `graph.microsoft.com`, `api.smith.langchain.com`) is not a placeholder; leave it.
- **Exception: a domain the code enforces.** When the code under test accepts only a
  provider's domain, keep the provider suffix and make `example` the leftmost label. A
  client that rejects any host outside `*.service-now.com` is tested with
  `example.service-now.com`.
