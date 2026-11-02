"""Tests for the ess-my-groups resolver and editor."""

import json
import os
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import my_groups  # noqa: E402 -- the script directory is not a package

_USAGE_ERROR = 2  # argparse's exit code for bad arguments

SEED = """\
# My groups -- keep this comment

[users.ada] # inline note
name = "Ada Lovelace"
aliases = ["Ada"]
email = "ada@example.com"

[users.grace]
name = "Grace Hopper"
email = "grace@example.com"

[groups.platform-team]
aliases = ["my pod"]
members = ["ada", "grace", "alan@example.com", "Mystery Person"]

[groups.my-team]
aliases = ["my team"]
members = ["ada", "jdoe@example.com"]
"""

HANDLES = """\
[users.ada]
name = "Ada Lovelace"
aliases = ["Ada"]
email = "ada@example.com"

[users.ada.handles]
github = ["ada_example", "ada_oss"]
webex = "ada@example.com"

[users.grace]
name = "Grace Hopper"

[groups.pod]
members = ["ada", "grace", "jdoe@example.com", "Nobody"]
"""


class _FakeStdin:
    def __init__(self, *, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


@pytest.fixture(name="config")
def fixture_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "groups.toml"
    monkeypatch.setenv(my_groups.CONFIG_ENV_VAR, str(path))
    monkeypatch.setattr(sys, "stdin", _FakeStdin(tty=False))
    return path


@pytest.fixture(name="seeded")
def fixture_seeded(config: Path) -> Path:
    config.write_text(SEED, encoding="utf-8")
    return config


@pytest.fixture(name="with_handles")
def fixture_with_handles(config: Path) -> Path:
    config.write_text(HANDLES, encoding="utf-8")
    return config


def _resolve(*names: str) -> dict:
    doc = my_groups.load_document(my_groups.get_config_path())
    return my_groups.resolve(doc, list(names))


def _keys(result: dict) -> list[str | None]:
    return [member["key"] or member["email"] for member in result["members"]]


def _load(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


# === Paths ===


def test_override_env_var_wins(tmp_path: Path) -> None:
    environ = {
        my_groups.CONFIG_ENV_VAR: str(tmp_path / "x.toml"),
        "XDG_CONFIG_HOME": "/elsewhere",
    }
    assert my_groups.get_config_path(environ) == tmp_path / "x.toml"


def test_absolute_xdg_config_home_is_used(tmp_path: Path) -> None:
    path = my_groups.get_config_path({"XDG_CONFIG_HOME": str(tmp_path)})
    assert path == tmp_path / "ess-my-groups" / "groups.toml"


@pytest.mark.parametrize("config_home", ["", "relative/config"])
def test_relative_or_unset_xdg_falls_back_to_home(
    config_home: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    path = my_groups.get_config_path({"XDG_CONFIG_HOME": config_home})
    assert path == tmp_path / ".config" / "ess-my-groups" / "groups.toml"


# === Names ===


def test_nickname_key_follows_rfc_8266() -> None:
    assert my_groups.nickname_key(" Platform \u3000 Team ") == "platform team"
    assert my_groups.nickname_key("Jean-Luc") != my_groups.nickname_key("Jean Luc")
    assert my_groups.nickname_key("Zoe\u0308") == my_groups.nickname_key("Zo\u00eb")
    assert my_groups.nickname_key("\ufb01le") == "file"


def test_handle_key_follows_rfc_8265() -> None:
    assert my_groups.handle_key(" Sam_Smith ") == "sam_smith"
    assert my_groups.handle_key("sam-smith") != my_groups.handle_key("sam_smith")
    assert my_groups.handle_key("\uff53\uff41\uff4d") == "sam"
    assert my_groups.handle_key("zoe\u0308") == my_groups.handle_key("zo\u00eb")


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("Alice.Smith@Example.COM", "alice.smith@example.com"),
        (" a-b@example.com ", "a-b@example.com"),
        ("@ada", None),
        ("ada@", None),
        ("a@b@example.com", None),
        ("a b@example.com", None),
        ("Ada", None),
        ('"a b"@example.com', '"a b"@example.com'),
        ("a@[192.0.2.1]", "a@[192.0.2.1]"),
        ("Jane@Example.com (work)", "jane@example.com"),
        ("a..b@example.com", None),
        (".a@example.com", None),
        ("a@example\n.com", None),
    ],
)
def test_email_key(text: str, key: str | None) -> None:
    assert my_groups.email_key(text) == key


def test_parse_email_keeps_case_and_drops_comments() -> None:
    assert my_groups.parse_email(" Jane@Example.com (work) ") == "Jane@Example.com"


@pytest.mark.parametrize(
    ("key", "problem"),
    [
        ("ada", None),
        ("user:ada", "can't start with"),
        ("Group: pod", "can't start with"),
        ("!!", "at least one ASCII"),
        ("", "at least one ASCII"),
    ],
)
def test_key_error(key: str, problem: str | None) -> None:
    error = my_groups.key_error(key)
    assert error == problem if problem is None else problem in error


@pytest.mark.parametrize(
    ("text", "split"),
    [
        ("user:ada", ("user", "ada")),
        ("GROUP: my pod", ("group", "my pod")),
        ("ada", (None, "ada")),
        ("team:ada", (None, "team:ada")),
        ("user:", (None, "user:")),
    ],
)
def test_split_kind(text: str, split: tuple[str | None, str]) -> None:
    assert my_groups.split_kind(text) == split


# === Resolution ===


@pytest.mark.usefixtures("seeded")
@pytest.mark.parametrize(
    "name", ["MY  POD", " my pod ", "Platform Team", "platform_team"]
)
def test_resolve_group_by_alias_or_key_spelling(name: str) -> None:
    assert _keys(_resolve(name)) == ["ada", "grace", "alan@example.com"]


def test_handles_differing_in_punctuation_name_different_users(config: Path) -> None:
    config.write_text(
        '[users.sam]\nname = "Sam"\n\n[users.sam.handles]\ngithub = ["sam_smith"]\n\n'
        '[users.pat]\nname = "Pat"\n\n[users.pat.handles]\nslack = ["sam-smith"]\n',
        encoding="utf-8",
    )
    assert my_groups.validate(my_groups.load_document(config))[0] == []
    assert _keys(_resolve("SAM_SMITH")) == ["sam"]
    assert _keys(_resolve("sam-smith")) == ["pat"]


def test_handle_lookup_does_not_fold_punctuation(config: Path) -> None:
    config.write_text(
        '[users.pat]\nname = "Pat"\n\n[users.pat.handles]\nslack = ["sam-smith"]\n',
        encoding="utf-8",
    )
    with pytest.raises(my_groups.NameNotFoundError, match="Did you mean: user:pat"):
        _resolve("sam_smith")


def test_handle_that_is_another_users_alias_is_refused(
    seeded: Path, capsys: pytest.CaptureFixture
) -> None:
    argv = ["user", "update", "grace", "--add-handle", "slack=ADA", "--yes"]
    assert my_groups.main(argv) == 1
    assert "already refers to user:ada" in capsys.readouterr().err
    assert seeded.read_text(encoding="utf-8") == SEED


def test_names_match_across_unicode_forms(config: Path) -> None:
    config.write_text('[users.zoe]\nname = "Zo\u00eb Smith"\n', encoding="utf-8")
    assert _keys(_resolve("zoe\u0308 smith")) == ["zoe"]


@pytest.mark.usefixtures("seeded")
def test_alias_punctuation_counts_but_gets_a_hint() -> None:
    with pytest.raises(my_groups.NameNotFoundError, match="group:platform-team"):
        _resolve("my-pod")


@pytest.mark.usefixtures("seeded")
def test_overlapping_groups_dedupe_shared_users() -> None:
    assert _keys(_resolve("my pod", "my team")) == [
        "ada",
        "grace",
        "alan@example.com",
        "jdoe@example.com",
    ]


@pytest.mark.usefixtures("seeded")
def test_undeclared_email_and_unresolved_name() -> None:
    result = _resolve("my pod")
    email_member = result["members"][2]
    assert email_member == {
        "key": None,
        "name": None,
        "aliases": [],
        "email": "alan@example.com",
        "handles": {},
    }
    assert result["unresolved"] == ["Mystery Person"]


@pytest.mark.usefixtures("with_handles")
def test_user_resolves_by_nickname_with_handles_by_service() -> None:
    (member,) = _resolve("ada")["members"]
    assert member["key"] == "ada"
    assert member["handles"] == {
        "github": ["ada_example", "ada_oss"],
        "webex": ["ada@example.com"],
    }


@pytest.mark.usefixtures("with_handles")
def test_handles_are_lookup_names() -> None:
    assert _keys(_resolve("ADA_EXAMPLE")) == ["ada"]


@pytest.mark.usefixtures("seeded")
def test_unknown_name_suggests_close_match() -> None:
    with pytest.raises(my_groups.NameNotFoundError, match="Did you mean: user:ada"):
        _resolve("adaa")


@pytest.mark.usefixtures("seeded")
def test_kind_prefix_limits_the_match() -> None:
    assert _keys(_resolve("user:Ada")) == ["ada"]
    assert _keys(_resolve("group:my team")) == ["ada", "jdoe@example.com"]
    with pytest.raises(my_groups.NameNotFoundError):
        _resolve("group:ada")


def test_kind_prefix_settles_a_name_shared_by_a_user_and_a_group(
    config: Path,
) -> None:
    config.write_text(
        '[users.pat]\nname = "Pat"\naliases = ["pod"]\n\n'
        '[groups.team]\naliases = ["pod"]\nmembers = ["x@example.com"]\n',
        encoding="utf-8",
    )
    with pytest.raises(my_groups.ConflictError, match="group:team, user:pat"):
        _resolve("pod")
    assert _keys(_resolve("user:pod")) == ["pat"]
    assert _keys(_resolve("group:pod")) == ["x@example.com"]


def test_emails_keep_punctuation_when_matching(config: Path) -> None:
    config.write_text(
        '[users.alice]\nname = "Alice"\nemail = "alice-smith@example.com"\n\n'
        '[groups.pod]\nmembers = ["alice_smith@example.com", '
        '"ALICE-SMITH@example.com"]\n',
        encoding="utf-8",
    )
    members = _resolve("pod")["members"]
    assert [(member["key"], member["email"]) for member in members] == [
        (None, "alice_smith@example.com"),
        ("alice", "alice-smith@example.com"),
    ]


def test_nested_groups_are_included(config: Path) -> None:
    config.write_text(
        '[groups.a]\nmembers = ["x@example.com"]\ngroups = ["b"]\n'
        '[groups.b]\nmembers = ["y@example.com"]\n',
        encoding="utf-8",
    )
    assert _keys(_resolve("a")) == ["x@example.com", "y@example.com"]


def test_group_cycle_is_an_error(config: Path) -> None:
    config.write_text(
        '[groups.a]\ngroups = ["b"]\n[groups.b]\ngroups = ["a"]\n', encoding="utf-8"
    )
    with pytest.raises(my_groups.ConfigError, match="cycle"):
        _resolve("a")
    errors, _ = my_groups.validate(my_groups.load_document(config))
    assert any("cycle" in error for error in errors)


def test_shared_nested_groups_are_walked_once(config: Path) -> None:
    layers = 25  # 2**25 paths from the top if each path is walked separately
    tables = [
        f'[groups.g{layer}{side}]\ngroups = ["g{layer + 1}a", "g{layer + 1}b"]\n'
        for layer in range(layers)
        for side in "ab"
    ]
    tables += [
        f'[groups.g{layers}{side}]\nmembers = ["{side}@example.com"]\n' for side in "ab"
    ]
    config.write_text("".join(tables), encoding="utf-8")
    assert my_groups.validate(my_groups.load_document(config)) == ([], [])
    assert _keys(_resolve("g0a")) == ["a@example.com", "b@example.com"]


def test_validate_reports_every_broken_nested_group(config: Path) -> None:
    config.write_text(
        '[groups.a]\naliases = ["Team A"]\ngroups = ["gone", "b", "lost"]\n'
        '[groups.b]\ngroups = ["Team A"]\n',
        encoding="utf-8",
    )
    errors, warnings = my_groups.validate(my_groups.load_document(config))
    assert errors == [
        "Group 'a' includes unknown group 'gone'.",
        "Group 'a' includes unknown group 'lost'.",
        "Group cycle: a -> b -> a.",
        "Group cycle: b -> a -> b.",
    ]
    assert warnings == ["Group 'b': nested group 'Team A' is group:a; store 'a'."]


# === Resolve output ===


@pytest.mark.usefixtures("with_handles")
def test_resolve_prints_one_handle_per_line(capsys: pytest.CaptureFixture) -> None:
    assert my_groups.main(["resolve", "pod", "--handle", "GitHub"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "ada_example\nada_oss\n"
    assert "no GitHub handle for Grace Hopper" in captured.err
    assert "no GitHub handle for jdoe@example.com" in captured.err
    assert "unresolved name 'Nobody'" in captured.err


@pytest.mark.usefixtures("with_handles")
def test_resolve_prints_one_email_per_line(capsys: pytest.CaptureFixture) -> None:
    assert my_groups.main(["resolve", "pod", "--email"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "ada@example.com\njdoe@example.com\n"
    assert "no email for Grace Hopper" in captured.err


def _card(uid: str, kind: str = "individual", **fields: object) -> dict:
    return {"@type": "Card", "version": "1.0", "uid": uid, "kind": kind, **fields}


@pytest.mark.usefixtures("with_handles")
def test_resolve_prints_jscontact_cards(capsys: pytest.CaptureFixture) -> None:
    assert my_groups.main(["resolve", "pod"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == [
        _card(
            "group:pod",
            "group",
            name={"full": "pod"},
            members={
                "user:ada": True,
                "user:grace": True,
                "mailto:jdoe@example.com": True,
            },
        ),
        _card(
            "user:ada",
            name={"full": "Ada Lovelace"},
            nicknames={"n1": {"name": "Ada"}},
            emails={"e1": {"address": "ada@example.com"}},
            onlineServices={
                "s1": {"service": "github", "user": "ada_example"},
                "s2": {"service": "github", "user": "ada_oss"},
                "s3": {"service": "webex", "user": "ada@example.com"},
            },
        ),
        _card("user:grace", name={"full": "Grace Hopper"}),
        _card(
            "mailto:jdoe@example.com", emails={"e1": {"address": "jdoe@example.com"}}
        ),
    ]
    assert "unresolved name 'Nobody'" in captured.err


def test_group_card_members_include_nested_groups(
    config: Path, capsys: pytest.CaptureFixture
) -> None:
    config.write_text(
        '[users.ada]\nname = "Ada"\n\n[users.grace]\nname = "Grace"\n\n'
        '[groups.team]\naliases = ["my team"]\nmembers = ["ada"]\ngroups = ["pod"]\n\n'
        '[groups.pod]\nmembers = ["grace", "ada"]\n',
        encoding="utf-8",
    )
    assert my_groups.main(["resolve", "my team", "pod"]) == 0
    cards = json.loads(capsys.readouterr().out)
    assert [card["uid"] for card in cards] == [
        "group:team",
        "group:pod",
        "user:ada",
        "user:grace",
    ]
    assert cards[0]["nicknames"] == {"n1": {"name": "my team"}}
    assert cards[0]["members"] == {"user:ada": True, "user:grace": True}
    assert cards[1]["members"] == {"user:grace": True, "user:ada": True}


@pytest.mark.usefixtures("with_handles")
@pytest.mark.parametrize(
    ("argv", "code"),
    [
        (["pod", "--handle", "github"], my_groups.EXIT_INCOMPLETE),
        (["ada", "--handle", "github"], 0),
        (["pod"], my_groups.EXIT_INCOMPLETE),
        (["ada", "grace"], 0),
        (["grace", "--email"], my_groups.EXIT_INCOMPLETE),
    ],
)
def test_strict_exits_nonzero_when_anything_is_missing(
    argv: list[str], code: int
) -> None:
    assert my_groups.main(["resolve", *argv]) == 0
    assert my_groups.main(["resolve", *argv, "--strict"]) == code


@pytest.mark.usefixtures("with_handles")
def test_null_ends_each_value_with_nul(capsys: pytest.CaptureFixture) -> None:
    assert my_groups.main(["resolve", "pod", "--handle", "github", "-0"]) == 0
    assert capsys.readouterr().out == "ada_example\0ada_oss\0"


@pytest.mark.usefixtures("with_handles")
def test_null_needs_a_line_mode() -> None:
    with pytest.raises(SystemExit) as exc:
        my_groups.main(["resolve", "pod", "--null"])
    assert exc.value.code == _USAGE_ERROR


# === Validation ===


def test_validate_reports_shared_alias_and_unresolved_member(config: Path) -> None:
    config.write_text(
        '[users.ada]\nname = "Ada"\naliases = ["pod"]\n'
        '[groups.team]\naliases = ["pod"]\nmembers = ["Nobody"]\n',
        encoding="utf-8",
    )
    errors, warnings = my_groups.validate(my_groups.load_document(config))
    assert any("'pod' refers to more than one entry" in error for error in errors)
    assert any("'Nobody'" in warning for warning in warnings)


def test_validate_reports_problems_on_stderr(
    config: Path, capsys: pytest.CaptureFixture
) -> None:
    config.write_text(
        '[users.ada]\nname = "Ada"\n\n[groups.a]\nmembers = ["Ada", "b"]\n\n'
        '[groups.b]\nmembers = ["ada"]\n',
        encoding="utf-8",
    )
    assert my_groups.main(["validate"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "warning: Group 'a': member 'Ada' is user:ada" in captured.err
    assert "error: Group 'a': member 'b' is group:b" in captured.err


def test_validate_flags_members_not_stored_by_key(config: Path) -> None:
    config.write_text(
        '[users.ada]\nname = "Ada"\nemail = "ada@example.com"\n\n'
        '[groups.a]\nmembers = ["Ada", "ada@example.com", "b"]\n\n'
        '[groups.b]\nmembers = ["ada"]\n',
        encoding="utf-8",
    )
    errors, warnings = my_groups.validate(my_groups.load_document(config))
    assert errors == ["Group 'a': member 'b' is group:b; list it in groups."]
    assert warnings == [
        "Group 'a': member 'Ada' is user:ada; store 'ada'.",
        "Group 'a': member 'ada@example.com' is user:ada; store 'ada'.",
    ]


def test_schema_rejects_non_string_values(config: Path) -> None:
    config.write_text("[users.ada]\nname = 3\n", encoding="utf-8")
    with pytest.raises(my_groups.ConfigError, match="users.ada.name"):
        my_groups.load_document(config)


@pytest.mark.parametrize(
    ("toml", "message"),
    [
        ('[groups.pod]\nmembers = "ada"\n', "groups.pod.members must be a list"),
        ('[groups.pod]\naliases = "pod"\n', "groups.pod.aliases must be a list"),
        (
            '[users.ada]\nemail = ["a@example.com"]\n',
            "users.ada.email must be a string",
        ),
        ('[users.ada]\nname = ["Ada"]\n', "users.ada.name must be a string"),
        ("[users.ada.handles]\ngithub = 3\n", "users.ada.handles.github must be"),
        ('[users.ada]\nhandles = "github"\n', "users.ada.handles must be a table"),
        ('[users.ada]\nhandles = ["github"]\n', "users.ada.handles must be a table"),
        ('[people.ada]\nname = "Ada"\n', "Unknown top-level entry 'people'"),
        ('[users.ada]\nemail = "ada@"\n', "users.ada.email is not an email address"),
        ('[users."user:ada"]\nname = "Ada"\n', "users.user:ada: a key can't start"),
        ('[groups."!!"]\nmembers = []\n', "groups.!!: a key needs at least one"),
    ],
)
def test_schema_checks_each_field_type(config: Path, toml: str, message: str) -> None:
    config.write_text(toml, encoding="utf-8")
    with pytest.raises(my_groups.ConfigError, match=message):
        my_groups.load_document(config)


def test_read_commands_report_missing_file(
    config: Path, capsys: pytest.CaptureFixture
) -> None:
    assert my_groups.main(["list"]) == 1
    assert "No groups file" in capsys.readouterr().err
    assert not config.exists()


# === Write safety ===

WRITE_COMMANDS = [
    ["user", "add", "Alan Turing", "--alias", "Alan"],
    ["user", "update", "ada", "--add-handle", "github=ada_example"],
    ["user", "remove", "grace"],
    ["group", "add", "reviewers", "--member", "ada"],
    ["group", "update", "my team", "--add-alias", "the team"],
    ["group", "add-member", "my team", "grace"],
    ["group", "remove-member", "my pod", "grace"],
    ["group", "remove", "my team"],
]


@pytest.mark.parametrize("argv", WRITE_COMMANDS, ids=lambda argv: " ".join(argv[:2]))
def test_dry_run_writes_nothing(
    argv: list[str], seeded: Path, capsys: pytest.CaptureFixture
) -> None:
    assert my_groups.main([*argv, "--dry-run"]) == 0
    assert seeded.read_text(encoding="utf-8") == SEED
    assert not seeded.with_name("groups.toml.bak").exists()
    assert "Dry run: nothing written." in capsys.readouterr().out


def test_dry_run_on_missing_file_creates_nothing(config: Path) -> None:
    assert my_groups.main(["user", "add", "Ada", "--dry-run"]) == 0
    assert not config.exists()
    assert not config.parent.joinpath("groups.toml.bak").exists()


@pytest.mark.parametrize("argv", WRITE_COMMANDS, ids=lambda argv: " ".join(argv[:2]))
def test_yes_skips_the_prompt(
    argv: list[str], seeded: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fail_prompt() -> str:
        raise AssertionError("--yes must not prompt")

    monkeypatch.setattr("builtins.input", _fail_prompt)
    assert my_groups.main([*argv, "--yes"]) == 0
    assert seeded.read_text(encoding="utf-8") != SEED


def test_write_without_tty_or_yes_fails(
    seeded: Path, capsys: pytest.CaptureFixture
) -> None:
    assert my_groups.main(["user", "add", "Alan Turing"]) == 1
    assert "--yes" in capsys.readouterr().err
    assert seeded.read_text(encoding="utf-8") == SEED


@pytest.mark.parametrize(
    ("answer", "written"), [("y", True), ("n", False), ("", False)]
)
def test_interactive_prompt_goes_to_stderr(
    answer: str,
    written: bool,
    seeded: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    monkeypatch.setattr(sys, "stdin", _FakeStdin(tty=True))
    monkeypatch.setattr("builtins.input", lambda: answer)
    my_groups.main(["user", "add", "Alan Turing"])
    assert "Write these changes" in capsys.readouterr().err
    assert (seeded.read_text(encoding="utf-8") != SEED) is written


def test_write_is_atomic_and_keeps_a_backup(seeded: Path) -> None:
    assert my_groups.main(["user", "add", "Alan Turing", "--yes"]) == 0
    assert seeded.with_name("groups.toml.bak").read_text(encoding="utf-8") == SEED
    leftovers = [path.name for path in seeded.parent.iterdir() if path.suffix == ".tmp"]
    assert leftovers == []


def test_write_through_a_symlink_keeps_the_link(config: Path) -> None:
    target = config.parent / "dotfiles" / "groups.toml"
    target.parent.mkdir()
    target.write_text(SEED, encoding="utf-8")
    config.symlink_to(target)
    assert my_groups.main(["user", "add", "Alan Turing", "--yes"]) == 0
    assert config.is_symlink()
    assert "alan-turing" in _load(target)["users"]
    assert target.with_name("groups.toml.bak").read_text(encoding="utf-8") == SEED


def test_file_changed_during_prompt_is_not_overwritten(
    seeded: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    other_edit = SEED + '\n[users.ada]\nname = "Ada"\n'

    def _edit_then_confirm() -> str:
        seeded.write_text(other_edit, encoding="utf-8")
        return "y"

    monkeypatch.setattr(sys, "stdin", _FakeStdin(tty=True))
    monkeypatch.setattr("builtins.input", _edit_then_confirm)
    assert my_groups.main(["user", "add", "Alan Turing"]) == 1
    assert "changed after this plan was made" in capsys.readouterr().err
    assert seeded.read_text(encoding="utf-8") == other_edit


def test_init_does_not_replace_a_file_created_during_prompt(
    config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _create_then_confirm() -> str:
        config.write_text(SEED, encoding="utf-8")
        return "y"

    monkeypatch.setattr(sys, "stdin", _FakeStdin(tty=True))
    monkeypatch.setattr("builtins.input", _create_then_confirm)
    assert my_groups.main(["init"]) == 1
    assert config.read_text(encoding="utf-8") == SEED


def _assert_lock_refuses_second_writer(
    path: Path, capsys: pytest.CaptureFixture
) -> None:
    with my_groups._write_lock(path):  # pylint: disable=protected-access
        assert my_groups.main(["user", "add", "Alan Turing", "--yes"]) == 1
    assert "in progress" in capsys.readouterr().err
    assert path.read_text(encoding="utf-8") == SEED
    assert my_groups.main(["user", "add", "Alan Turing", "--yes"]) == 0


def test_second_writer_is_refused_while_the_lock_is_held(
    seeded: Path, capsys: pytest.CaptureFixture
) -> None:
    _assert_lock_refuses_second_writer(seeded, capsys)


class _FakeMsvcrt:
    """Stands in for Windows ``msvcrt``: one lock on byte 0, refused while held."""

    LK_NBLCK = 2
    LK_UNLCK = 0

    def __init__(self) -> None:
        self.held = False

    def locking(self, fd: int, mode: int, nbytes: int) -> None:
        assert os.lseek(fd, 0, os.SEEK_CUR) == 0
        assert nbytes == 1
        if mode == self.LK_UNLCK:
            self.held = False
        elif self.held:
            raise OSError("locked")
        else:
            self.held = True


def test_windows_lock_refuses_second_writer(
    seeded: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakeMsvcrt()
    monkeypatch.setattr(my_groups, "fcntl", None)
    monkeypatch.setattr(my_groups, "msvcrt", fake)
    _assert_lock_refuses_second_writer(seeded, capsys)
    assert not fake.held


def test_writes_are_refused_without_file_locking(
    seeded: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(my_groups, "fcntl", None)
    monkeypatch.setattr(my_groups, "msvcrt", None)
    assert my_groups.main(["user", "add", "Alan Turing", "--yes"]) == 1
    assert "no file locking" in capsys.readouterr().err
    assert seeded.read_text(encoding="utf-8") == SEED
    assert my_groups.main(["user", "add", "Alan Turing", "--dry-run"]) == 0


def test_change_that_creates_an_ambiguous_name_is_refused(
    seeded: Path, capsys: pytest.CaptureFixture
) -> None:
    argv = ["group", "add", "reviewers", "--alias", "Alice", "--member", "Alice"]
    assert my_groups.main([*argv, "--yes"]) == 1
    err = capsys.readouterr().err
    assert "would leave the file inconsistent" in err
    assert "'alice' refers to more than one entry" in err
    assert seeded.read_text(encoding="utf-8") == SEED


def test_existing_errors_do_not_block_unrelated_changes(config: Path) -> None:
    config.write_text(
        '[users.pat]\nname = "Pat"\naliases = ["pod"]\n\n'
        '[groups.team]\naliases = ["pod"]\nmembers = ["pat"]\n',
        encoding="utf-8",
    )
    assert my_groups.main(["user", "add", "Ada", "--yes"]) == 0
    assert "ada" in _load(config)["users"]


# === Editing users ===


def test_first_add_creates_file_and_directory(
    tmp_path: Path, config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nested = tmp_path / "deep" / "groups.toml"
    monkeypatch.setenv(my_groups.CONFIG_ENV_VAR, str(nested))
    assert my_groups.main(["user", "add", "Ada", "--yes"]) == 0
    assert _load(nested) == {"users": {"ada": {"name": "Ada"}}}
    assert not config.exists()


@pytest.mark.parametrize(
    "argv",
    [
        ["user", "add", "Someone", "--alias", "ADA"],
        ["user", "add", "Someone", "--email", "Ada@example.com"],
        ["user", "add", "Ada Lovelace", "--key", "other"],
        ["user", "add", "Someone", "--key", "my-team"],
        ["user", "add", "Someone", "--handle", "slack=ada"],
    ],
)
def test_user_add_rejects_taken_names(
    argv: list[str], seeded: Path, capsys: pytest.CaptureFixture
) -> None:
    assert my_groups.main([*argv, "--yes"]) == 1
    assert "already" in capsys.readouterr().err
    assert seeded.read_text(encoding="utf-8") == SEED


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["user", "add", "Ada", "--email", "ada@"], "is not an email address"),
        (["user", "update", "ada", "--email", "a..b@example.com"], "is not an email"),
        (["user", "add", "Ada", "--key", "user:ada"], "can't start with"),
        (["user", "add", "Ada", "--key", "!!"], "at least one ASCII"),
        (["group", "add", "x", "--key", "group:x", "--member", "ada"], "can't start"),
    ],
)
def test_writes_reject_bad_emails_and_keys(
    argv: list[str], message: str, seeded: Path, capsys: pytest.CaptureFixture
) -> None:
    assert my_groups.main([*argv, "--yes"]) == 1
    assert message in capsys.readouterr().err
    assert seeded.read_text(encoding="utf-8") == SEED


def test_emails_are_stored_and_printed_as_addr_specs(
    seeded: Path, capsys: pytest.CaptureFixture
) -> None:
    argv = ["user", "add", "Zoe", "--email", " Zoe@Example.com (work) ", "--yes"]
    assert my_groups.main(argv) == 0
    argv = ["group", "add-member", "my team", "New@Example.org (new)", "--yes"]
    assert my_groups.main(argv) == 0
    data = _load(seeded)
    assert data["users"]["zoe"]["email"] == "Zoe@Example.com"
    assert data["groups"]["my-team"]["members"][-1] == "New@Example.org"
    capsys.readouterr()
    assert my_groups.main(["resolve", "my team", "--email"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "New@Example.org"


def test_user_add_with_handles(config: Path) -> None:
    argv = ["user", "add", "Katherine Johnson", "--key", "katherine"]
    handles = ["--handle", "GitHub=katherine_example", "--handle", "github=octocat"]
    assert (
        my_groups.main([*argv, *handles, "--handle", "webex=m@example.com", "--yes"])
        == 0
    )
    assert _load(config)["users"]["katherine"] == {
        "name": "Katherine Johnson",
        "handles": {
            "github": ["katherine_example", "octocat"],
            "webex": ["m@example.com"],
        },
    }
    assert _keys(_resolve("octocat")) == ["katherine"]


@pytest.mark.parametrize("bad", ["github", "=octocat", "github="])
def test_handle_flag_needs_service_and_user(config: Path, bad: str) -> None:
    with pytest.raises(SystemExit):
        my_groups.main(["user", "add", "Ada", "--handle", bad])
    assert not config.exists()


def test_user_update_sets_and_clears_fields(seeded: Path) -> None:
    argv = ["user", "update", "ada", "--add-handle", "github=ada_example"]
    assert my_groups.main([*argv, "--email", "", "--add-alias", "S", "--yes"]) == 0
    assert _load(seeded)["users"]["ada"] == {
        "name": "Ada Lovelace",
        "aliases": ["Ada", "S"],
        "handles": {"github": ["ada_example"]},
    }


def test_user_update_removes_one_handle_or_a_whole_service(
    with_handles: Path,
) -> None:
    argv = ["user", "update", "ada", "--remove-handle", "github=ADA_OSS", "--yes"]
    assert my_groups.main(argv) == 0
    assert _load(with_handles)["users"]["ada"]["handles"] == {
        "github": ["ada_example"],
        "webex": "ada@example.com",
    }
    argv = ["user", "update", "ada", "--remove-handle", "github"]
    assert my_groups.main([*argv, "--remove-handle", "webex", "--yes"]) == 0
    assert "handles" not in _load(with_handles)["users"]["ada"]


def test_single_string_handle_is_upgraded_on_edit(with_handles: Path) -> None:
    argv = ["user", "update", "ada", "--add-handle", "webex=ada@example.net", "--yes"]
    assert my_groups.main(argv) == 0
    assert _load(with_handles)["users"]["ada"]["handles"]["webex"] == [
        "ada@example.com",
        "ada@example.net",
    ]


def test_handles_differing_only_in_punctuation_are_separate_accounts(
    with_handles: Path,
) -> None:
    argv = ["user", "update", "ada", "--add-handle", "github=ada-example", "--yes"]
    assert my_groups.main(argv) == 0
    argv = ["user", "update", "ada", "--remove-handle", "github=ADA_example", "--yes"]
    assert my_groups.main(argv) == 0
    assert _load(with_handles)["users"]["ada"]["handles"]["github"] == [
        "ada_oss",
        "ada-example",
    ]


def test_edits_merge_service_names_that_differ_only_in_case(config: Path) -> None:
    config.write_text(
        '[users.ada]\nname = "Ada"\n\n[users.ada.handles]\n'
        'github = ["a"]\nGitHub = ["b", "A"]\n',
        encoding="utf-8",
    )
    argv = ["user", "update", "ada", "--add-handle", "GITHUB=c", "--yes"]
    assert my_groups.main(argv) == 0
    assert _load(config)["users"]["ada"]["handles"] == {"github": ["a", "b", "c"]}
    config.write_text(
        '[users.ada]\nname = "Ada"\n\n[users.ada.handles]\n'
        'github = ["a"]\nGitHub = "b"\nslack = "s"\n',
        encoding="utf-8",
    )
    argv = ["user", "update", "ada", "--remove-handle", "github", "--yes"]
    assert my_groups.main(argv) == 0
    assert _load(config)["users"]["ada"]["handles"] == {"slack": "s"}


def test_email_aliases_keep_their_punctuation(config: Path) -> None:
    config.write_text(
        '[users.alice]\nname = "Alice"\naliases = ["alice-smith@example.com"]\n',
        encoding="utf-8",
    )
    argv = ["user", "update", "alice", "--yes"]
    assert my_groups.main([*argv, "--add-alias", "alice_smith@example.com"]) == 0
    assert my_groups.main([*argv, "--remove-alias", "ALICE-smith@example.com"]) == 0
    assert _load(config)["users"]["alice"]["aliases"] == ["alice_smith@example.com"]


def test_new_handles_table_lands_under_the_user(with_handles: Path) -> None:
    argv = ["user", "update", "grace", "--add-handle", "github=grace_example", "--yes"]
    assert my_groups.main(argv) == 0
    text = with_handles.read_text(encoding="utf-8")
    assert (
        '[users.grace]\nname = "Grace Hopper"\n\n[users.grace.handles]\n'
        'github = ["grace_example"]\n'
    ) in text
    assert _load(with_handles)["groups"]["pod"]["members"][1] == "grace"


def test_handle_cannot_belong_to_two_users(
    seeded: Path, capsys: pytest.CaptureFixture
) -> None:
    argv = ["user", "update", "ada", "--add-handle", "github=g_shared", "--yes"]
    assert my_groups.main(argv) == 0
    argv = ["user", "update", "grace", "--add-handle", "slack=g_shared", "--yes"]
    assert my_groups.main(argv) == 1
    assert "already refers to user:ada" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("member", "update"),
    [
        ("ada@example.com", ["--email", "ada.l@example.com"]),
        ("ada@example.com", ["--email", ""]),
        ("Ada Lovelace", ["--name", "Ada B Lovelace"]),
        ("Ada", ["--remove-alias", "Ada"]),
        ("ada_example", ["--remove-handle", "github=ada_example"]),
        ("ada_example", ["--remove-handle", "github"]),
    ],
)
def test_changing_a_lookup_name_keeps_group_members_attached(
    config: Path, member: str, update: list[str]
) -> None:
    config.write_text(
        '[users.ada]\nname = "Ada Lovelace"\naliases = ["Ada"]\n'
        'email = "ada@example.com"\n\n[users.ada.handles]\n'
        'github = ["ada_example"]\n\n'
        f'[groups.pod]\nmembers = ["{member}"]\n',
        encoding="utf-8",
    )
    assert my_groups.main(["user", "update", "ada", *update, "--yes"]) == 0
    assert _load(config)["groups"]["pod"]["members"] == ["ada"]
    assert _keys(_resolve("pod")) == ["ada"]


def test_user_remove_cascades_into_groups(seeded: Path) -> None:
    assert my_groups.main(["user", "remove", "Ada", "--yes"]) == 0
    data = _load(seeded)
    assert "ada" not in data["users"]
    assert data["groups"]["platform-team"]["members"] == [
        "grace",
        "alan@example.com",
        "Mystery Person",
    ]
    assert data["groups"]["my-team"]["members"] == ["jdoe@example.com"]


# === Editing groups ===


def test_add_member_creates_stub_with_hint(
    seeded: Path, capsys: pytest.CaptureFixture
) -> None:
    assert my_groups.main(["group", "add-member", "my team", "Adaa", "--yes"]) == 0
    assert "Did you mean: user:ada?" in capsys.readouterr().out
    data = _load(seeded)
    assert data["users"]["adaa"] == {"name": "Adaa"}
    assert data["groups"]["my-team"]["members"] == ["ada", "jdoe@example.com", "adaa"]


def test_add_member_skips_existing_member_by_any_name(
    seeded: Path, capsys: pytest.CaptureFixture
) -> None:
    assert my_groups.main(["group", "add-member", "my pod", "ada@example.com"]) == 0
    assert "No changes." in capsys.readouterr().out
    assert seeded.read_text(encoding="utf-8") == SEED


def test_add_member_resolves_a_prefixed_email_or_refuses_it(
    seeded: Path, capsys: pytest.CaptureFixture
) -> None:
    argv = ["group", "add-member", "my team", "user:GRACE@example.com", "--yes"]
    assert my_groups.main(argv) == 0
    assert _load(seeded)["groups"]["my-team"]["members"][-1] == "grace"
    argv = ["group", "add-member", "my team", "user:new@example.com", "--yes"]
    assert my_groups.main(argv) == 1
    assert "pass the bare address" in capsys.readouterr().err
    assert "new@example.com" not in seeded.read_text(encoding="utf-8")


def test_hand_edited_prefixed_email_resolves_bare_and_warns(config: Path) -> None:
    config.write_text(
        '[groups.a]\nmembers = ["user:new@example.com"]\n', encoding="utf-8"
    )
    assert _keys(_resolve("a")) == ["new@example.com"]
    _, warnings = my_groups.validate(my_groups.load_document(config))
    assert warnings == [
        "Group 'a': no user has the email in 'user:new@example.com'; "
        "store the bare address."
    ]


@pytest.mark.parametrize("member", ["my pod", "group:my pod"])
def test_add_member_rejects_a_group_name(seeded: Path, member: str) -> None:
    assert my_groups.main(["group", "add-member", "my team", member, "--yes"]) == 1
    assert seeded.read_text(encoding="utf-8") == SEED


def test_group_add_requires_members(seeded: Path) -> None:
    assert my_groups.main(["group", "add", "empty", "--yes"]) == 1
    assert seeded.read_text(encoding="utf-8") == SEED


def test_group_add_keeps_display_name_as_alias(seeded: Path) -> None:
    argv = ["group", "add", "R&D Leads", "--member", "grace", "--include", "my team"]
    assert my_groups.main([*argv, "--yes"]) == 0
    assert _load(seeded)["groups"]["r-d-leads"] == {
        "aliases": ["R&D Leads"],
        "members": ["grace"],
        "groups": ["my-team"],
    }


def test_group_update_rejects_a_cycle(seeded: Path) -> None:
    assert (
        my_groups.main(["group", "update", "my pod", "--include", "my team", "--yes"])
        == 0
    )
    assert (
        my_groups.main(["group", "update", "my team", "--include", "my pod", "--yes"])
        == 1
    )
    assert "groups" not in _load(seeded)["groups"]["my-team"]


def test_removing_a_group_alias_keeps_nested_references_attached(
    seeded: Path,
) -> None:
    argv = ["group", "update", "my team", "--include", "platform-team", "--yes"]
    assert my_groups.main(argv) == 0
    text = seeded.read_text(encoding="utf-8")
    seeded.write_text(
        text.replace('groups = ["platform-team"]', 'groups = ["my pod"]'),
        encoding="utf-8",
    )
    argv = ["group", "update", "platform-team", "--remove-alias", "my pod", "--yes"]
    assert my_groups.main(argv) == 0
    data = _load(seeded)
    assert data["groups"]["my-team"]["groups"] == ["platform-team"]
    assert "aliases" not in data["groups"]["platform-team"]
    assert my_groups.validate(my_groups.load_document(seeded))[0] == []


def test_group_remove_drops_nested_references(seeded: Path) -> None:
    assert (
        my_groups.main(["group", "update", "my pod", "--include", "my team", "--yes"])
        == 0
    )
    assert my_groups.main(["group", "remove", "my team", "--yes"]) == 0
    data = _load(seeded)
    assert set(data["groups"]) == {"platform-team"}
    assert "groups" not in data["groups"]["platform-team"]
    assert "ada" in data["users"]


# === File format ===


def test_edit_preserves_comments_and_order(seeded: Path) -> None:
    argv = ["user", "update", "grace", "--add-alias", "Gracie", "--yes"]
    assert my_groups.main(argv) == 0
    text = seeded.read_text(encoding="utf-8")
    assert text.startswith("# My groups -- keep this comment\n")
    assert '[users.ada] # inline note\nname = "Ada Lovelace"' in text
    headers = [line for line in text.splitlines() if line.startswith("[")]
    assert [header.split(" #")[0] for header in headers] == [
        "[users.ada]",
        "[users.grace]",
        "[groups.platform-team]",
        "[groups.my-team]",
    ]
    assert tomllib.loads(text)["users"]["grace"]["aliases"] == ["Gracie"]


def test_special_characters_round_trip(config: Path) -> None:
    name = 'Zoë "Z" O\'Brien \\ Jr.'
    argv = ["user", "add", name, "--key", "zoe.obrien", "--alias", "Zoë"]
    assert my_groups.main([*argv, "--yes"]) == 0
    assert _load(config)["users"]["zoe.obrien"] == {"name": name, "aliases": ["Zoë"]}
    (member,) = _resolve("zoë")["members"]
    assert member["name"] == name


def test_blank_line_cleanup_never_changes_a_multiline_value(config: Path) -> None:
    name = "Ada\n\n\n[team]"
    config.write_text(
        f'[users.ada]\nname = """{name}"""\n\n\n\n[users.grace]\nname = "Grace"\n',
        encoding="utf-8",
    )
    argv = ["user", "update", "grace", "--add-alias", "Gracie", "--yes"]
    assert my_groups.main(argv) == 0
    assert _load(config)["users"]["ada"]["name"] == name


def test_init_writes_a_valid_example_and_never_overwrites(
    config: Path, capsys: pytest.CaptureFixture
) -> None:
    assert my_groups.main(["init", "--yes"]) == 0
    errors, _ = my_groups.validate(my_groups.load_document(config))
    assert errors == []
    assert my_groups.main(["init", "--yes"]) == 1
    assert "never overwrites" in capsys.readouterr().err
