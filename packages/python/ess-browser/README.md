# ess-browser

Shared Playwright browser session with SSO handling.

```python
from ess_browser import SsoSite, open_authenticated_page, should_use_headed_browser

SITE = SsoSite(url="https://app.example.com/dashboard")
PROFILE = "~/.my-tool/browser-profile"

headed = should_use_headed_browser(SITE, profile_dir=PROFILE)

with open_authenticated_page(SITE, headed=headed, profile_dir=PROFILE) as page:
    print(page.title())
```

The first run opens a window so you can complete SSO; later runs reuse
the saved session and stay headless.

## Installation

From the workspace root:

```bash
uv sync --all-packages
```

## API

### `SsoSite`

Frozen dataclass describing one SSO-protected site. Declare it once as a
module constant instead of threading the same keyword arguments through
every call.

| Field | Default | Description |
|---|---|---|
| `url` | *required* | Page to open; its host means "authenticated" |
| `login_complete_url` | `None` | Where the IdP lands, when that is not `url` |
| `settle_ms` | `0` | Grace period before judging an SSO redirect |
| `nav_timeout_ms` | `60_000` | Navigation timeout |
| `extra_auth_domains` | `()` | IdP hosts beyond `AUTH_DOMAINS` |

Set `settle_ms` for sites that redirect from client-side JavaScript, where
the first load briefly lands on the app before bouncing to the IdP. Set
`login_complete_url` when the callback always returns to one canonical
host, otherwise waiting on `url` never finishes. Use `extra_auth_domains`
for a tenant's own IdP rather than widening the shared tuple.

### `open_authenticated_page(site, *, headed, profile_dir=None, prepare=None)`

Context manager yielding a page that has completed SSO: it navigates,
waits out any IdP redirect, and returns to `site.url` if login landed
elsewhere. Raises `SsoTimeoutError` if login never completes. Pass
`prepare` to attach listeners before the first navigation, which would
otherwise miss that navigation's own traffic.

### `should_use_headed_browser(site, *, profile_dir, force_headed=False, force_headless=False)`

Probes the saved session and returns whether a visible window is needed.
Raises `ValueError` if both force flags are set. Callers that prefer a
`--headless` default with a retry on SSO expiry can skip this helper and
just retry `open_authenticated_page` headed when login times out.

### `BrowserSession`

Context manager that launches a persistent Chrome browser session.

| Parameter | Default | Description |
|---|---|---|
| `headed` | `False` | Show the browser window |
| `profile_dir` | `~/.ess-browser/profile` | Browser profile for session persistence |
| `viewport` | `1280x900` | Browser viewport size |
| `enable_extensions` | `False` | Load Chrome extensions from the profile (headed mode only) |
| `init_scripts` | `[]` | Additional JS snippets injected into every page |
| `skip_duo_update_prompt` | `True` | Auto-dismiss the Duo "update Chrome" nag |

Methods:

- `new_page() -> Page` -- open a new browser tab
- `wait_for_login(page, target_url, timeout_ms=300_000)` -- block until SSO completes
- `is_auth_redirect(current_url, target_url, *, extra_auth_domains=()) -> bool` --
  check if on an SSO page

#### Duo prompt auto-dismiss

By default, an init script auto-clicks the "Skip for now" button on
`duosecurity.com` pages so the Chrome-update nag doesn't block automated
flows. Pass `skip_duo_update_prompt=False` to disable this behavior for
manual or debugging sessions.

#### Chrome extensions

Set `enable_extensions=True` to load extensions installed in the profile
directory. This only has an effect in headed mode; Playwright ignores
extensions when running headless.

### Profile directories

- `default_profile_dir(tool_name) -> Path` -- `~/.<tool_name>/browser-profile`
- `profile_dir_display(tool_name) -> str` -- the same path in tilde form,
  for `--help` text that should not print the running user's name

Each tool gets its own directory on purpose: one expired session should
not force a re-login everywhere.

#### Session cookies

`BrowserSession` carries session-scoped cookies across launches itself,
in `<profile_dir>/session-cookies.json` (written `0600`, owner-only).

This is not belt-and-braces. The cookie that represents a completed
SSO login, often a `JSESSIONID` on the IdP's host, is session-scoped,
and Chrome restores those only under "continue where you left off",
which Playwright does not set. Without this, a persistent profile keeps
everything *except* the thing that keeps you logged in, and every launch
repeats the IdP round trip.

Only session-scoped cookies are stored. Anything with a real expiry is
already in Chrome's own store, and duplicating it would give one cookie
two sources of truth. Saved cookies older than 12 hours are dropped
rather than replayed, and every step is best effort: a failure here
costs one login, never the run.

A tool that opens more than one browser per command still pays for a
login per launch, because the session cookie is only written on clean
exit. Prefer one session per run and share the context.

### Exceptions

- `EssBrowserError` -- base class for everything this package raises
- `SsoTimeoutError` -- login did not complete before the timeout
- `sso_timeout_message(*, headed, prefix=..., retry_hint=...)` -- builds the
  message, appending the retry hint only when it is actionable. The hint
  defaults to "re-run with `--headed`"; pass `retry_hint` if your CLI spells
  that differently so operators are not sent to a flag you do not have

Callers are expected to catch `SsoTimeoutError` and re-raise it as their
own domain error; the message already carries the actionable hint.

### `ess_browser.auth`

Lower-level SSO detection functions:

- `AUTH_DOMAINS` -- tuple of public SSO/IdP domain patterns. It names no
  company's own login hosts; pass those as `extra_auth_domains`
- `DUO_SKIP_UPDATE_SCRIPT` -- JS snippet that dismisses the Duo update prompt
- `LOGIN_TIMEOUT_MS` -- login wait timeout (5 minutes)
- `NAV_TIMEOUT_MS` -- default navigation timeout (60 seconds)
- `SSO_SETTLE_MS` -- default redirect grace period (5 seconds)
- `is_auth_redirect(current_url, target_url, *, extra_auth_domains=()) -> bool`
- `is_sso_login_required(target_url, *, profile_dir, ...) -> bool`
- `wait_for_login(page, target_url, timeout_ms=LOGIN_TIMEOUT_MS)`

`AUTH_DOMAINS` includes substring patterns (`sso.`, `idp.`, `adfs.`), so
host matching is deliberately loose.
