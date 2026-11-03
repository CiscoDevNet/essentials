---
description: >-
  Use example.com, example.net, example.org, or example.edu, a subdomain of
  one, or a name under the reserved .example, .invalid, or .test TLDs for every
  illustrative host, URL, and email in code, tests, comments, and docs.
applyTo: "**"
---

# Example URLs

Placeholder hosts, URLs, and email addresses use a reserved name, which no one can
register:

| Reserved | Names |
| -------- | ----- |
| Documentation domains | `example.com`, `example.net`, `example.org`, `example.edu`, and their subdomains |
| Top-level domains | Any name under `.example`, `.invalid`, or `.test` |

RFC 2606 reserves `example.com`, `example.net`, `example.org`, and the three top-level
domains. IANA holds all four documentation domains, and each serves a page that reads:
"This domain is for use in documentation examples without needing permission." The
top-level domains are never delegated, so names under them never resolve.

| Placeholder for | Use | Not |
| --------------- | --- | --- |
| A remote host | `host.example.com` | `host.com`, `myhost` |
| An identity provider | `idp.example.com` | `login.vendor.com` |
| A deployed app | `app.example.com` | `my-app.awsapprunner.com` |
| A person | `ada@example.com` | an address at `x.com` or a real company |
| A second organization | `corp.example.net` | `corp.example.io` |
| A host that must never resolve | `unreachable.invalid` | `nonexistent.com` |
| A throwaway test identity | `test@example.invalid` | an address at `test.com` |

- **Default to `example.com`.** Use `example.net`, `example.org`, or `example.edu` when an
  example needs organizations that are visibly distinct.
- **Use a reserved top-level domain when its meaning helps.** `.invalid` marks a value
  that must never resolve or be delivered, such as an unreachable host in a failure test
  or a git identity in a throwaway repo. `.test` suits hosts on a local test network, and
  `.example` reads as an illustration.
- **Only these.** Other `example.<tld>` names, such as `example.io` or `example.dev`, and
  look-alikes such as `test.com`, are ordinary domains someone can register.
- **Real endpoints stay real.** A host the code actually calls (`github.com`,
  `graph.microsoft.com`, `api.smith.langchain.com`) is not a placeholder; leave it.
- **Exception: a domain the code enforces.** When the code under test accepts only a
  provider's domain, keep the provider suffix and make `example` the leftmost label. A
  client that rejects any host outside `*.service-now.com` is tested with
  `example.service-now.com`.
