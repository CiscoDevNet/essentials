# ess-browser

Shared Playwright browser session with SSO handling.

```python
from ess_browser import BrowserSession

with BrowserSession(headed=True) as session:
    page = session.new_page()
    page.goto("https://example.com/")
    session.wait_for_login(page, "https://example.com/")
```

## Installation

From the workspace root:

```bash
uv sync --all-packages
```

## API

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
- `is_auth_redirect(current_url, target_url) -> bool` -- check if on an SSO page

#### Duo prompt auto-dismiss

By default, an init script auto-clicks the "Skip for now" button on
`duosecurity.com` pages so the Chrome-update nag doesn't block automated
flows. Pass `skip_duo_update_prompt=False` to disable this behavior for
manual or debugging sessions.

#### Chrome extensions

Set `enable_extensions=True` to load extensions installed in the profile
directory. This only has an effect in headed mode; Playwright ignores
extensions when running headless.

### `ess_browser.auth`

Lower-level SSO detection functions:

- `AUTH_DOMAINS` -- tuple of known SSO/IdP domain patterns
- `DUO_SKIP_UPDATE_SCRIPT` -- JS snippet that dismisses the Duo update prompt
- `LOGIN_TIMEOUT_MS` -- default timeout (5 minutes)
- `is_auth_redirect(current_url, target_url) -> bool`
- `wait_for_login(page, target_url, timeout_ms=LOGIN_TIMEOUT_MS)`
