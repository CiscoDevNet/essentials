# SPDX-License-Identifier: Apache-2.0
"""OAuth 2.0 Authorization Code Flow with PKCE against any OIDC provider.

Opens a browser for the user to authenticate, captures the callback on a
temporary local HTTP server, exchanges the code for tokens, and prints the
access token (JWT) to stdout for copy-paste.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import os
import secrets
import sys
import time
import webbrowser
from http import HTTPStatus
from http.client import HTTP_PORT
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from dotenv import load_dotenv

_DEFAULT_REDIRECT_URI = "http://localhost:8900/auth/callback"
_DEFAULT_SCOPE = "openid"

_REQUEST_TIMEOUT = 30
_CALLBACK_TIMEOUT = 120


class _AuthCodeError(Exception):
    """Raised when the authorization code flow fails."""


@dataclasses.dataclass(frozen=True)
class _OidcClient:
    """OIDC provider endpoints and client credentials."""

    authorize_url: str
    token_url: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str


def _generate_pkce() -> tuple[str, str]:
    """Return ``(code_verifier, code_challenge)`` for PKCE (S256)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _make_callback_handler(
    expected_state: str,
    result: dict[str, str | None],
) -> type[BaseHTTPRequestHandler]:
    """Return a request handler class that captures the OAuth callback."""

    class _CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            query = parse_qs(urlparse(self.path).query)

            returned_state = query.get("state", [None])[0]
            if returned_state != expected_state:
                self._respond(
                    HTTPStatus.BAD_REQUEST,
                    "OAuth state mismatch -- possible CSRF attack",
                )
                return

            if "error" in query:
                result["error"] = (
                    f"{query['error'][0]}: "
                    f"{query.get('error_description', ['unknown'])[0]}"
                )
                self._respond(HTTPStatus.BAD_REQUEST, result["error"])
                return

            result["code"] = query.get("code", [None])[0]
            if not result["code"]:
                result["error"] = "No authorization code in callback"
                self._respond(HTTPStatus.BAD_REQUEST, result["error"])
                return

            self._respond(
                HTTPStatus.OK,
                "Authenticated! You can close this tab.",
            )

        def _respond(self, status: HTTPStatus, body: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    return _CallbackHandler


def _bind_callback_server(port: int, expected_state: str) -> tuple[HTTPServer, dict]:
    """Bind the callback server so it is ready before the browser opens."""
    result: dict[str, str | None] = {"code": None, "error": None}
    handler_cls = _make_callback_handler(expected_state, result)
    try:
        server = HTTPServer(("localhost", port), handler_cls)
    except OSError as exc:
        raise _AuthCodeError(f"Could not bind to localhost:{port}: {exc}") from exc
    return server, result


def _capture_callback(port: int, expected_state: str) -> str:
    """Bind a server and wait for the OAuth callback."""
    server, result = _bind_callback_server(port, expected_state)
    return _wait_for_callback(server, result)


def _wait_for_callback(server: HTTPServer, result: dict) -> str:
    """Wait for the OAuth callback on an already-bound server."""
    deadline = time.monotonic() + _CALLBACK_TIMEOUT
    try:
        while result["code"] is None and result["error"] is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _AuthCodeError(
                    f"No callback received within {_CALLBACK_TIMEOUT}s"
                )
            server.timeout = remaining
            server.handle_request()
    finally:
        server.server_close()

    if result["error"]:
        raise _AuthCodeError(result["error"])
    if not result["code"]:
        raise _AuthCodeError("No authorization code received")
    return result["code"]


def _exchange_code(
    client: _OidcClient,
    code: str,
    code_verifier: str,
) -> dict:
    """Exchange an authorization code for tokens."""
    with httpx.Client(timeout=_REQUEST_TIMEOUT) as http:
        response = http.post(
            client.token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": client.client_id,
                "client_secret": client.client_secret,
                "code": code,
                "redirect_uri": client.redirect_uri,
                "code_verifier": code_verifier,
            },
        )
    if response.status_code != HTTPStatus.OK:
        raise _AuthCodeError(f"Token exchange failed: {response.text}")
    return response.json()


def _require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        print(  # noqa: T201
            f"Error: set {name} in .env (see .env.example)",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


def main() -> None:
    """Run the authorization code flow and print the resulting token."""
    load_dotenv()

    client = _OidcClient(
        authorize_url=_require_env("OIDC_AUTHORIZE_URL"),
        token_url=_require_env("OIDC_TOKEN_URL"),
        client_id=_require_env("OIDC_CLIENT_ID"),
        client_secret=_require_env("OIDC_CLIENT_SECRET"),
        redirect_uri=os.environ.get("OIDC_REDIRECT_URI", _DEFAULT_REDIRECT_URI),
        scope=os.environ.get("OIDC_SCOPE", _DEFAULT_SCOPE),
    )
    parsed_uri = urlparse(client.redirect_uri)
    if parsed_uri.scheme != "http":
        print(  # noqa: T201
            f"Error: only http:// redirect URIs are supported"
            f" (got {parsed_uri.scheme}://)",
            file=sys.stderr,
        )
        sys.exit(1)
    port = parsed_uri.port or HTTP_PORT

    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = _generate_pkce()

    params = urlencode(
        {
            "client_id": client.client_id,
            "response_type": "code",
            "redirect_uri": client.redirect_uri,
            "scope": client.scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    auth_url = f"{client.authorize_url}?{params}"

    try:
        server, result = _bind_callback_server(port, expected_state=state)
    except _AuthCodeError as exc:
        print(f"Error: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    print("Opening browser for OIDC login...", file=sys.stderr)  # noqa: T201
    if not webbrowser.open(auth_url):
        print(  # noqa: T201
            f"Could not open browser. Visit this URL manually:\n{auth_url}",
            file=sys.stderr,
        )

    print(  # noqa: T201
        f"Waiting for callback on localhost:{port} ...",
        file=sys.stderr,
    )

    try:
        code = _wait_for_callback(server, result)
    except _AuthCodeError as exc:
        print(f"Error: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    print("Exchanging code for token...", file=sys.stderr)  # noqa: T201

    try:
        token_data = _exchange_code(client, code, code_verifier)
    except _AuthCodeError as exc:
        print(f"Error: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(1)
    except httpx.RequestError as exc:
        print(  # noqa: T201
            f"Error: network failure during token exchange: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", "unknown")

    print("", file=sys.stderr)  # noqa: T201
    print("--- ACCESS TOKEN (copy below this line) ---", file=sys.stderr)  # noqa: T201
    print(access_token)  # noqa: T201
    print("--- END TOKEN ---", file=sys.stderr)  # noqa: T201
    print(f"\nExpires in: {expires_in}s", file=sys.stderr)  # noqa: T201
    print(  # noqa: T201
        f"Token type: {token_data.get('token_type', 'unknown')}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
