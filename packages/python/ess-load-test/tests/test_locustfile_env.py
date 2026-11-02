"""Unit tests for locust environment helpers."""

from ess_load_test.locust.runtime import (
    apply_auth_header,
    apply_auth_to_client,
    default_profile_for_scenario,
    is_auth_redirect,
    mark_response_failure,
    normalize_locust_host,
    parse_load_test_paths,
    read_auth_header,
    read_load_test_duration,
    read_load_test_spawn_rate,
    read_load_test_users,
)


class TestParseLoadTestPaths:
    def test_default_path(self):
        assert parse_load_test_paths(None) == ("/",)

    def test_multiple_paths(self):
        assert parse_load_test_paths("/healthz, /api/health") == (
            "/healthz",
            "/api/health",
        )

    def test_empty_string_uses_default(self):
        assert parse_load_test_paths("  ,  ") == ("/",)


class TestNormalizeLocustHost:
    def test_strips_trailing_slash(self) -> None:
        url = "https://app.example.com/"
        assert normalize_locust_host(url) == "https://app.example.com"

    def test_preserves_bare_host(self) -> None:
        url = "https://app.example.com"
        assert normalize_locust_host(url) == url


class TestApplyAuthHeader:
    def test_bearer_value(self):
        headers: dict[str, str] = {}
        apply_auth_header(headers, "Bearer example-token")
        assert headers["Authorization"] == "Bearer example-token"

    def test_named_header(self):
        headers: dict[str, str] = {}
        apply_auth_header(headers, "X-API-KEY: secret")
        assert headers["X-API-KEY"] == "secret"

    def test_none_is_noop(self):
        headers = {"Existing": "1"}
        apply_auth_header(headers, None)
        assert headers == {"Existing": "1"}


class TestApplyAuthToClient:
    def test_cookie_header_populates_cookie_jar(self):
        class Cookies:
            def __init__(self) -> None:
                self.values: dict[str, str] = {}

            def clear(self) -> None:
                self.values.clear()

            def set(self, name: str, value: str) -> None:
                self.values[name] = value

        class Client:
            def __init__(self) -> None:
                self.headers: dict[str, str] = {}
                self.cookies = Cookies()

        client = Client()
        apply_auth_to_client(
            client,
            "Cookie: session=abc123; other=xyz",
        )
        assert client.headers["Cookie"] == "session=abc123; other=xyz"
        assert client.cookies.values == {
            "session": "abc123",
            "other": "xyz",
        }


class TestReadAuthHeader:
    def test_prefers_synced_file(self, tmp_path, monkeypatch) -> None:
        auth_file = tmp_path / "auth.txt"
        auth_file.write_text("Cookie: session=from-file", encoding="utf-8")
        monkeypatch.setenv("LOAD_TEST_AUTH_HEADER_FILE", str(auth_file))
        monkeypatch.setenv("LOAD_TEST_AUTH_HEADER", "Cookie: session=from-env")
        assert read_auth_header() == "Cookie: session=from-file"


class TestIsAuthRedirect:
    def test_redirect_status_codes(self) -> None:
        assert is_auth_redirect(307) is True
        assert is_auth_redirect(200) is False


class TestMarkResponseFailureEnv:
    def test_ok_status_not_marked(self):
        class Response:
            status_code = 200

            def failure(self, _message: str) -> None:
                raise AssertionError("should not fail")

        mark_response_failure(Response(), strict=True)


class TestDefaultProfileForScenario:
    def test_mixed_scenario(self) -> None:
        assert default_profile_for_scenario("mixed") == "mixed-run"

    def test_pages_scenario(self) -> None:
        assert default_profile_for_scenario("pages") == "pages-run"

    def test_default_scenario(self) -> None:
        assert default_profile_for_scenario("default") == "smoke"


class TestLoadTestEnvReaders:
    _expected_users = 50
    _expected_spawn_rate = 5.0

    def test_read_load_test_users(self, monkeypatch) -> None:
        monkeypatch.delenv("LOAD_TEST_USERS", raising=False)
        monkeypatch.delenv("LOCUST_USERS", raising=False)
        assert read_load_test_users() is None

        monkeypatch.setenv("LOAD_TEST_USERS", str(self._expected_users))
        assert read_load_test_users() == self._expected_users

    def test_read_load_test_spawn_rate(self, monkeypatch) -> None:
        monkeypatch.setenv("LOAD_TEST_SPAWN_RATE", str(int(self._expected_spawn_rate)))
        assert read_load_test_spawn_rate() == self._expected_spawn_rate

    def test_read_load_test_duration(self, monkeypatch) -> None:
        monkeypatch.setenv("LOAD_TEST_DURATION", "10m")
        assert read_load_test_duration() == "10m"
