# ess-hello-jwt-auth-code

Obtain a JWT access token from any [OpenID Connect](https://openid.net/developers/how-connect-works/)
provider via the [OAuth 2.0 Authorization Code Flow](https://datatracker.ietf.org/doc/html/rfc6749#section-4.1)
with [PKCE](https://datatracker.ietf.org/doc/html/rfc7636).

Run the script, log in through your browser, and copy the printed token.

```bash
uv run ess-hello-jwt-auth-code
# Opens browser -> provider login -> prints token to stdout
```

Expected output:

```
Opening browser for OIDC login...
Waiting for callback on localhost:8900 ...
Exchanging code for token...

--- ACCESS TOKEN (copy below this line) ---
eyJhbGciOiJSUzI1NiIs...
--- END TOKEN ---

Expires in: 3600s
Token type: Bearer
```

The token is printed to **stdout** (status messages go to stderr), so you
can pipe it directly:

```bash
uv run ess-hello-jwt-auth-code > token.txt
```

## Installation

From the workspace root:

```bash
uv sync --all-packages
```

## Configuration

From the example directory:

```bash
cd examples/python/ess-hello-jwt-auth-code
```

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Register a **web** app with your OpenID Connect provider configured for:

- **Grant type**: Authorization Code (with PKCE)
- **Redirect URI**: `http://localhost:8900/auth/callback`

The `OIDC_AUTHORIZE_URL` and `OIDC_TOKEN_URL` values come from your
provider's OpenID Connect discovery document, typically published at
`<issuer>/.well-known/openid-configuration`. Provider documentation:

- Okta: <https://developer.okta.com/docs/reference/api/oidc/>
- Auth0: <https://auth0.com/docs/authenticate/protocols/openid-connect-protocol>
- Microsoft Entra: <https://learn.microsoft.com/entra/identity-platform/v2-protocols-oidc>
- Google: <https://developers.google.com/identity/openid-connect/openid-connect>
- Keycloak: <https://www.keycloak.org/docs/latest/server_admin/index.html#con-oidc_server_administration_guide>

| Variable             | Required | Description                                                | Default                                  |
| -------------------- | -------- | ---------------------------------------------------------- | ---------------------------------------- |
| `OIDC_AUTHORIZE_URL` | Yes      | Provider's authorization endpoint (where the user logs in) | --                                       |
| `OIDC_TOKEN_URL`     | Yes      | Provider's token endpoint (where the code is exchanged)    | --                                       |
| `OIDC_CLIENT_ID`     | Yes      | OAuth 2.0 client ID issued by the provider                 | --                                       |
| `OIDC_CLIENT_SECRET` | Yes      | OAuth 2.0 client secret issued by the provider             | --                                       |
| `OIDC_SCOPE`         | No       | Scopes to request (space-separated)                        | `openid`                                 |
| `OIDC_REDIRECT_URI`  | No       | Local callback URL (port is parsed from this value)        | `http://localhost:8900/auth/callback`    |

## How it works

1. Generates a fresh PKCE `code_verifier` / `code_challenge` and a CSRF
   `state` value.
2. Opens the provider's authorization URL in your default browser.
3. Spins up a one-shot HTTP listener on `localhost` to capture the
   redirect callback.
4. Validates the returned `state` matches what was sent.
5. Exchanges the authorization code (plus the `code_verifier`) at the
   token endpoint for an access token.
6. Prints the access token to stdout; status messages go to stderr.

## License

[Apache 2.0](https://choosealicense.com/licenses/apache-2.0/)
