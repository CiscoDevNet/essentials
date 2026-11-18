#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit==0.14.0"]
# ///
"""Resolve and edit the personal users-and-groups file used by ess-my-groups.

The file lives at ``$XDG_CONFIG_HOME/ess-my-groups/groups.toml``, or
``~/.config/ess-my-groups/groups.toml`` when ``XDG_CONFIG_HOME`` is unset or relative.
``ESS_MY_GROUPS_FILE`` overrides the path.
"""

import argparse
import difflib
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager, nullcontext
from dataclasses import dataclass, field, replace
from email.errors import HeaderParseError
from email.headerregistry import Address
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:
    fcntl = None
try:
    import msvcrt
except ImportError:
    msvcrt = None

import tomlkit
from tomlkit.exceptions import ParseError
from tomlkit.toml_document import TOMLDocument

CONFIG_ENV_VAR = "ESS_MY_GROUPS_FILE"
_APP_DIR = "ess-my-groups"
_FILE_NAME = "groups.toml"
_EXAMPLE_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "groups.example.toml"
)
_HEADER_LINES = (
    "Personal users and groups for the ess-my-groups agent skill.",
    "Edit with `my_groups.py user ...` and `my_groups.py group ...`, or by hand.",
)
_SECTIONS = ("users", "groups")
_KINDS = ("user", "group")
_TEXT_FIELDS = frozenset({"name", "email"})
_LIST_FIELDS = frozenset({"aliases", "members", "groups"})
_HANDLES = "handles"
_JSCONTACT_VERSION = "1.0"
EXIT_INCOMPLETE = 3
_HINT_CUTOFF = 0.75
_WIDTH_TAGS = ("<wide>", "<narrow>")
_YES_ANSWERS = frozenset({"y", "yes"})

Identity = tuple[str, str]
Mutation = Callable[[TOMLDocument], list[str]]
# (rule, compared value); the rule is "key", "name", "handle", or "email".
IndexKey = tuple[str, str]


class MyGroupsError(Exception):
    """Base error for the groups file and its commands."""


class ConfigError(MyGroupsError):
    """The groups file is missing or malformed."""


class NameNotFoundError(MyGroupsError):
    """No user or group matches the given name."""


class ConflictError(MyGroupsError):
    """A name is ambiguous or already belongs to another entry."""


class AbortedError(MyGroupsError):
    """The operator declined the confirmation prompt."""


@dataclass(frozen=True, order=True)
class Entry:
    """A user or group, written ``user:<key>`` or ``group:<key>``."""

    kind: str
    key: str

    def __str__(self) -> str:
        return f"{self.kind}:{self.key}"


@dataclass(frozen=True)
class Handle:
    """A username on an online service; ``user`` is ``None`` for "every handle"."""

    service: str
    user: str | None = None


@dataclass(frozen=True)
class WriteOptions:
    """Flags shared by every write command."""

    dry_run: bool = False
    yes: bool = False


@dataclass(frozen=True)
class UserInput:
    """Fields for a new user."""

    name: str
    aliases: list[str] = field(default_factory=list)
    email: str | None = None
    handles: list[Handle] = field(default_factory=list)
    key: str | None = None


@dataclass(frozen=True)
class UserUpdate:
    """Changes to a user. ``email=""`` clears the email; ``None`` keeps it."""

    name: str | None = None
    add_aliases: list[str] = field(default_factory=list)
    remove_aliases: list[str] = field(default_factory=list)
    email: str | None = None
    add_handles: list[Handle] = field(default_factory=list)
    remove_handles: list[Handle] = field(default_factory=list)


@dataclass(frozen=True)
class _ListEdit:
    field: str
    noun: str
    add: list[str]
    remove: list[str]


@dataclass(frozen=True)
class GroupInput:
    """Fields for a new group."""

    name: str
    aliases: list[str] = field(default_factory=list)
    members: list[str] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)
    key: str | None = None


@dataclass(frozen=True)
class GroupUpdate:
    """Changes to an existing group's aliases and nested groups."""

    add_aliases: list[str] = field(default_factory=list)
    remove_aliases: list[str] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)
    excludes: list[str] = field(default_factory=list)


# === Names and paths ===


def nickname_key(text: str) -> str:
    """Compare a name or alias as an RFC 8266 nickname.

    Runs of whitespace become one space and the ends are trimmed, case is folded, and
    the result is NFKC-normalized. Punctuation counts: ``Jean-Luc`` is not
    ``Jean Luc``.
    """
    return unicodedata.normalize("NFKC", " ".join(text.split()).casefold())


def handle_key(text: str) -> str:
    """Compare a handle as an RFC 8265 case-mapped username.

    Full-width and half-width characters are mapped to their normal forms, case is
    folded, and the result is NFC-normalized. Punctuation counts: ``sam-smith`` and
    ``sam_smith`` are different accounts.
    """
    narrowed = "".join(
        unicodedata.normalize("NFKC", char)
        if unicodedata.decomposition(char).startswith(_WIDTH_TAGS)
        else char
        for char in text.strip()
    )
    return unicodedata.normalize("NFC", narrowed.casefold())


def parse_email(text: str) -> str | None:
    """Return ``text`` as a canonical RFC 5322 addr-spec, or ``None`` if it isn't one.

    Comments and surrounding whitespace are dropped, so ``jane@example.com (work)``
    becomes ``jane@example.com``. JSContact requires this form for email addresses.
    """
    try:
        address = Address(addr_spec=unicodedata.normalize("NFC", text.strip()))
    except (ValueError, IndexError, HeaderParseError):
        return None
    return address.addr_spec


def email_key(text: str) -> str | None:
    """Return the lookup key for an email address, or ``None`` if ``text`` isn't one.

    Only case is ignored; the local part keeps its punctuation, so ``a-b@x`` and
    ``a_b@x`` differ.
    """
    address = parse_email(text)
    return address.casefold() if address else None


def checked_email(value: str | None) -> str | None:
    """Return a new email value in canonical form; ``""`` and ``None`` pass through.

    Raises:
        MyGroupsError: ``value`` is not an RFC 5322 address.
    """
    if not value:
        return value
    address = parse_email(value)
    if address is None:
        raise MyGroupsError(f"'{value}' is not an email address.")
    return address


def alias_key(text: str) -> str:
    """Compare an alias: as an email if it is one, otherwise as a nickname."""
    return email_key(text) or nickname_key(text)


def split_kind(text: str) -> tuple[str | None, str]:
    """Split an optional ``user:`` or ``group:`` prefix off a name."""
    prefix, sep, rest = text.partition(":")
    kind = prefix.strip().casefold()
    if sep and kind in _KINDS and rest.strip():
        return kind, rest.strip()
    return None, text


def slugify(text: str) -> str:
    """Turn a display name into an ASCII key, e.g. ``platform-team``."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.casefold()).strip("-")


# Keys are slugs, so a key and a query compare as slugs: "platform team" finds
# platform-team. Names and handles keep their punctuation.
_RULES: dict[str, Callable[[str], str]] = {
    "key": slugify,
    "name": nickname_key,
    "handle": handle_key,
}


def _index_key(rule: str, term: str) -> IndexKey | None:
    """Return the index key for a stored ``term``; any email is compared as one."""
    email = email_key(term)
    if email:
        return ("email", email)
    value = _RULES[rule](term)
    return (rule, value) if value else None


def _query_keys(term: str) -> list[IndexKey]:
    """Return every index key a lookup of ``term`` can match, one per rule."""
    email = email_key(term)
    if email:
        return [("email", email)]
    return [
        (rule, value) for rule, compare in _RULES.items() if (value := compare(term))
    ]


def get_config_path(environ: Mapping[str, str] | None = None) -> Path:
    """Return the groups file path.

    ``ESS_MY_GROUPS_FILE`` wins; otherwise an absolute ``XDG_CONFIG_HOME`` is used, and
    a relative or unset one falls back to ``~/.config`` as the XDG spec requires.
    """
    env = os.environ if environ is None else environ
    override = env.get(CONFIG_ENV_VAR, "")
    if override:
        return Path(override).expanduser()
    config_home = env.get("XDG_CONFIG_HOME", "")
    base = Path(config_home) if os.path.isabs(config_home) else Path.home() / ".config"
    return base / _APP_DIR / _FILE_NAME


# === Loading ===


def _new_document() -> TOMLDocument:
    doc = tomlkit.document()
    for line in _HEADER_LINES:
        doc.add(tomlkit.comment(line))
    doc.add(tomlkit.nl())
    return doc


def _value_error(location: str, name: str, value: Any) -> str | None:
    is_text = isinstance(value, str)
    is_text_list = isinstance(value, list) and all(
        isinstance(item, str) for item in value
    )
    if name in _TEXT_FIELDS:
        if not is_text:
            return f"{location} must be a string."
        if name == "email" and value.strip() and parse_email(value) is None:
            return f"{location} is not an email address: {value!r}."
        return None
    if name in _LIST_FIELDS:
        return None if is_text_list else f"{location} must be a list of strings."
    if is_text or is_text_list:
        return None
    return f"{location} must be a string or a list of strings."


def _entry_errors(section: str, location: str, entry: Any) -> list[str]:
    errors: list[str] = []
    for name, value in entry.items():
        if section == "users" and name == _HANDLES:
            if not isinstance(value, dict):
                errors.append(
                    f"{location}.{name} must be a table, such as "
                    f'[{location}.{name}] with github = ["login"].'
                )
                continue
            errors.extend(
                error
                for service, logins in value.items()
                if (error := _value_error(f"{location}.{name}.{service}", "", logins))
            )
            continue
        error = _value_error(f"{location}.{name}", name, value)
        if error:
            errors.append(error)
    return errors


def _check_schema(doc: TOMLDocument) -> None:
    for name in doc:
        if name not in _SECTIONS:
            raise ConfigError(
                f"Unknown top-level entry '{name}'; expected [users.<key>] and "
                "[groups.<key>] tables."
            )
    for section in _SECTIONS:
        tables = doc.get(section, {})
        if not isinstance(tables, dict):
            raise ConfigError(f"[{section}] must be a table.")
        for key, entry in tables.items():
            if not isinstance(entry, dict):
                raise ConfigError(f"{section}.{key} must be a table.")
            key_problem = key_error(key)
            if key_problem:
                raise ConfigError(f"{section}.{key}: {key_problem}")
            errors = _entry_errors(section, f"{section}.{key}", entry)
            if errors:
                raise ConfigError(errors[0])


def key_error(key: str) -> str | None:
    """Return why ``key`` can't be a user or group key, or ``None`` if it can."""
    if split_kind(key)[0]:
        return "a key can't start with 'user:' or 'group:'."
    if not slugify(key):
        return "a key needs at least one ASCII letter or digit."
    return None


def load_document(path: Path, *, missing_ok: bool = False) -> TOMLDocument:
    """Parse the groups file; with ``missing_ok``, a missing file yields a new one."""
    if not path.exists():
        if missing_ok:
            return _new_document()
        raise ConfigError(
            f"No groups file at {path}. Add someone with `user add`, or run `init`."
        )
    try:
        doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    except ParseError as exc:
        raise ConfigError(f"{path} is not valid TOML: {exc}") from exc
    _check_schema(doc)
    return doc


def _users(doc: TOMLDocument) -> Any:
    return doc.get("users", {})


def _groups(doc: TOMLDocument) -> Any:
    return doc.get("groups", {})


def _section(doc: TOMLDocument, name: str) -> Any:
    if name not in doc:
        doc[name] = tomlkit.table(is_super_table=True)
    return doc[name]


def _text(entry: Any, name: str) -> str:
    return str(entry.get(name, ""))


def _texts(entry: Any, name: str) -> list[str]:
    return [str(item) for item in entry.get(name, [])]


def _handles(user: Any) -> dict[str, list[str]]:
    """Return a user's handles by service; a single string counts as one handle."""
    found: dict[str, list[str]] = {}
    for service, value in user.get(_HANDLES, {}).items():
        logins = [value] if isinstance(value, str) else value
        found.setdefault(service.casefold(), []).extend(
            str(login) for login in logins if login
        )
    return found


# === Lookup ===


def entry_terms(doc: TOMLDocument) -> Iterator[tuple[Entry, str, str]]:
    """Yield ``(entry, rule, term)`` for every lookup name in the file."""
    for key, user in _users(doc).items():
        entry = Entry("user", key)
        yield entry, "key", key
        for term in (
            _text(user, "name"),
            _text(user, "email"),
            *_texts(user, "aliases"),
        ):
            yield entry, "name", term
        for logins in _handles(user).values():
            for login in logins:
                yield entry, "handle", login
    for key, group in _groups(doc).items():
        entry = Entry("group", key)
        yield entry, "key", key
        for alias in _texts(group, "aliases"):
            yield entry, "name", alias


def build_index(doc: TOMLDocument) -> dict[IndexKey, set[Entry]]:
    """Map every lookup name (key, name, alias, email, handle) to what it names."""
    index: dict[IndexKey, set[Entry]] = {}
    for entry, rule, term in entry_terms(doc):
        index_key = _index_key(rule, term) if term else None
        if index_key:
            index.setdefault(index_key, set()).add(entry)
    return index


def lookup(index: dict[IndexKey, set[Entry]], term: str) -> set[Entry]:
    """Return every entry ``term`` names under any rule."""
    found: set[Entry] = set()
    for index_key in _query_keys(term):
        found |= index.get(index_key, set())
    return found


def _describe(entries: set[Entry]) -> str:
    return ", ".join(str(entry) for entry in sorted(entries))


def find_entry(
    index: dict[IndexKey, set[Entry]], text: str, kind: str | None = None
) -> Entry | None:
    """Return the entry ``text`` names, ``None`` if none; raise if it names several.

    A ``user:`` or ``group:`` prefix on ``text`` limits the match to that kind.
    """
    prefix, name = split_kind(text)
    if prefix and kind and prefix != kind:
        raise ConflictError(f"'{text}' names a {prefix}, but a {kind} is needed here.")
    wanted = prefix or kind
    matches = lookup(index, name)
    if wanted:
        matches = {entry for entry in matches if entry.kind == wanted}
    if len(matches) > 1:
        raise ConflictError(
            f"'{text}' matches more than one entry ({_describe(matches)}); "
            "use one of those."
        )
    return next(iter(matches), None)


def suggest(index: dict[IndexKey, set[Entry]], text: str) -> list[str]:
    """Return entries, as ``user:<key>`` or ``group:<key>``, named close to ``text``."""
    by_value: dict[str, set[Entry]] = {}
    for (_, value), entries in index.items():
        by_value.setdefault(value, set()).update(entries)
    close = {
        match
        for _, value in _query_keys(split_kind(text)[1])
        for match in difflib.get_close_matches(
            value, by_value, n=3, cutoff=_HINT_CUTOFF
        )
    }
    return sorted({str(entry) for match in close for entry in by_value[match]})


def _hint(index: dict[IndexKey, set[Entry]], text: str) -> str:
    hints = suggest(index, text)
    return f" Did you mean: {', '.join(hints)}?" if hints else ""


def _require(index: dict[IndexKey, set[Entry]], text: str, kind: str) -> Entry:
    entry = find_entry(index, text, kind=kind)
    if entry is None:
        raise NameNotFoundError(f"No {kind} named '{text}'.{_hint(index, text)}")
    return entry


def member_identity(index: dict[IndexKey, set[Entry]], member: str) -> Identity:
    """Classify a member string as a known user, an undeclared email, or a name."""
    entry = find_entry(index, member, kind="user")
    if entry:
        return ("user", entry.key)
    name = split_kind(member)[1]
    email = email_key(name)
    if email:
        return ("email", email)
    return ("name", nickname_key(name))


# === Resolution ===


def expand_group(
    doc: TOMLDocument,
    index: dict[IndexKey, set[Entry]],
    key: str,
    trail: tuple[str, ...] = (),
    done: set[str] | None = None,
) -> list[str]:
    """Return the member strings of a group, followed by those of its nested groups.

    A group reached by more than one path is expanded only once.
    """
    if key in trail:
        raise ConfigError(f"Group cycle: {' -> '.join((*trail, key))}.")
    done = set() if done is None else done
    group = _groups(doc)[key]
    members = _texts(group, "members")
    for nested in _texts(group, "groups"):
        nested_entry = find_entry(index, nested, kind="group")
        if nested_entry is None:
            raise ConfigError(f"Group '{key}' includes unknown group '{nested}'.")
        if nested_entry.key not in done:
            members.extend(
                expand_group(doc, index, nested_entry.key, (*trail, key), done)
            )
    done.add(key)
    return members


def _member_record(doc: TOMLDocument, identity: Identity, raw: str) -> dict[str, Any]:
    kind, value = identity
    if kind == "email":
        return {
            "key": None,
            "name": None,
            "aliases": [],
            "email": parse_email(split_kind(raw)[1]),
            "handles": {},
        }
    user = _users(doc)[value]
    return {
        "key": value,
        "name": _text(user, "name") or None,
        "aliases": _texts(user, "aliases"),
        "email": parse_email(_text(user, "email")),
        "handles": _handles(user),
    }


def _collect(
    doc: TOMLDocument, index: dict[IndexKey, set[Entry]], raw_members: list[str]
) -> tuple[list[dict], list[str]]:
    members: list[dict] = []
    unresolved: list[str] = []
    seen: set[Identity] = set()
    for raw in raw_members:
        identity = member_identity(index, raw)
        if identity in seen:
            continue
        seen.add(identity)
        if identity[0] == "name":
            unresolved.append(raw.strip())
        else:
            members.append(_member_record(doc, identity, raw))
    return members, unresolved


def resolve(doc: TOMLDocument, names: list[str]) -> dict[str, Any]:
    """Resolve user or group names to deduplicated users and unresolved names."""
    index = build_index(doc)
    raw_members: list[str] = []
    matched: list[str] = []
    for name in names:
        entry = find_entry(index, name)
        if entry is None:
            raise NameNotFoundError(
                f"No user or group named '{name}'.{_hint(index, name)}"
            )
        matched.append(str(entry))
        if entry.kind == "group":
            raw_members.extend(expand_group(doc, index, entry.key))
        else:
            raw_members.append(entry.key)
    members, unresolved = _collect(doc, index, raw_members)
    return {
        "query": names,
        "matched": matched,
        "members": members,
        "unresolved": unresolved,
    }


# === JSContact output ===


def _card(uid: str, kind: str) -> dict[str, Any]:
    return {"@type": "Card", "version": _JSCONTACT_VERSION, "uid": uid, "kind": kind}


def _numbered(prefix: str, values: Iterable[dict[str, str]]) -> dict[str, Any]:
    return {f"{prefix}{number}": value for number, value in enumerate(values, 1)}


def _nicknames(aliases: list[str]) -> dict[str, Any]:
    return _numbered("n", ({"name": alias} for alias in aliases))


def _member_uid(member: dict[str, Any]) -> str:
    return f"user:{member['key']}" if member["key"] else f"mailto:{member['email']}"


def _user_card(member: dict[str, Any]) -> dict[str, Any]:
    card = _card(_member_uid(member), "individual")
    if member["name"]:
        card["name"] = {"full": member["name"]}
    if member["aliases"]:
        card["nicknames"] = _nicknames(member["aliases"])
    if member["email"]:
        card["emails"] = {"e1": {"address": member["email"]}}
    services = [
        {"service": service, "user": login}
        for service, logins in member["handles"].items()
        for login in logins
    ]
    if services:
        card["onlineServices"] = _numbered("s", services)
    return card


def _group_card(
    doc: TOMLDocument, index: dict[IndexKey, set[Entry]], key: str
) -> dict[str, Any]:
    card = _card(f"group:{key}", "group")
    card["name"] = {"full": key}
    aliases = _texts(_groups(doc)[key], "aliases")
    if aliases:
        card["nicknames"] = _nicknames(aliases)
    members, _ = _collect(doc, index, expand_group(doc, index, key))
    card["members"] = {_member_uid(member): True for member in members}
    return card


def to_jscontact(doc: TOMLDocument, result: dict[str, Any]) -> list[dict[str, Any]]:
    """Return ``resolve`` output as JSContact (RFC 9553) Cards.

    Each named group becomes a group Card whose ``members`` lists every user in it,
    nested groups included. Every user's Card follows once, in resolution order.
    Unresolved names have no Card; callers report them separately.
    """
    index = build_index(doc)
    groups = [
        _group_card(doc, index, key)
        for kind, key in map(split_kind, result["matched"])
        if kind == "group"
    ]
    return groups + [_user_card(member) for member in result["members"]]


def _ambiguity_errors(
    doc: TOMLDocument, index: dict[IndexKey, set[Entry]]
) -> list[str]:
    """Report every stored name whose lookup, under any rule, finds several entries."""
    errors: set[str] = set()
    for _, _, term in entry_terms(doc):
        entries = lookup(index, term) if term else set()
        if len(entries) > 1:
            errors.add(f"'{term}' refers to more than one entry: {_describe(entries)}.")
    return sorted(errors)


def _member_problem(
    index: dict[IndexKey, set[Entry]], group_key: str, member: str
) -> tuple[str, str] | None:
    """Return ``("error" | "warning", message)`` for one stored member, or ``None``."""
    label = f"Group '{group_key}'"
    try:
        kind, value = member_identity(index, member)
        entry = find_entry(index, member) if kind == "name" else None
    except MyGroupsError as exc:
        return "error", f"{label}: {exc}"
    if entry is not None and entry.kind == "group":
        return "error", f"{label}: member '{member}' is {entry}; list it in groups."
    if kind == "name":
        return "warning", f"{label}: '{member}' is not a known user or an email."
    if kind == "user" and member != value:
        return (
            "warning",
            f"{label}: member '{member}' is user:{value}; store '{value}'.",
        )
    if kind == "email" and split_kind(member)[0]:
        return (
            "warning",
            f"{label}: no user has the email in '{member}'; store the bare address.",
        )
    return None


def _nested_entry(index: dict[IndexKey, set[Entry]], text: str) -> Entry | None:
    try:
        return find_entry(index, text, kind="group")
    except MyGroupsError:
        return None


def _find_cycle(
    doc: TOMLDocument,
    index: dict[IndexKey, set[Entry]],
    key: str,
    trail: tuple[str, ...] = (),
    done: set[str] | None = None,
) -> tuple[str, ...] | None:
    """Return the first nesting cycle through ``key``, skipping broken references.

    ``done`` holds groups already explored without a cycle, so each is walked once.
    """
    if key in trail:
        return (*trail, key)
    done = set() if done is None else done
    for nested in _texts(_groups(doc)[key], "groups"):
        entry = _nested_entry(index, nested)
        if entry is None or entry.key in done:
            continue
        cycle = _find_cycle(doc, index, entry.key, (*trail, key), done)
        if cycle:
            return cycle
    done.add(key)
    return None


def _nested_problems(
    doc: TOMLDocument, index: dict[IndexKey, set[Entry]], key: str
) -> tuple[list[str], list[str]]:
    """Check each nested-group reference of ``key`` on its own."""
    errors: list[str] = []
    warnings: list[str] = []
    for nested in _texts(_groups(doc)[key], "groups"):
        try:
            entry = find_entry(index, nested, kind="group")
        except MyGroupsError as exc:
            errors.append(f"Group '{key}': {exc}")
            continue
        if entry is None:
            errors.append(f"Group '{key}' includes unknown group '{nested}'.")
        elif nested != entry.key:
            warnings.append(
                f"Group '{key}': nested group '{nested}' is {entry}; "
                f"store '{entry.key}'."
            )
    cycle = _find_cycle(doc, index, key)
    if cycle:
        errors.append(f"Group cycle: {' -> '.join(cycle)}.")
    return errors, warnings


def _group_problems(
    doc: TOMLDocument, index: dict[IndexKey, set[Entry]], key: str
) -> tuple[list[str], list[str]]:
    errors, warnings = _nested_problems(doc, index, key)
    for member in _texts(_groups(doc)[key], "members"):
        problem = _member_problem(index, key, member)
        if problem:
            (errors if problem[0] == "error" else warnings).append(problem[1])
    return errors, warnings


def validate(doc: TOMLDocument) -> tuple[list[str], list[str]]:
    """Return ``(errors, warnings)`` for ambiguous names, bad nesting, and unknowns."""
    index = build_index(doc)
    errors = _ambiguity_errors(doc, index)
    warnings: list[str] = []
    for key in _groups(doc):
        group_errors, group_warnings = _group_problems(doc, index, key)
        errors.extend(group_errors)
        warnings.extend(group_warnings)
    return list(dict.fromkeys(errors)), warnings


# === Mutations ===


def _ensure_terms_free(
    index: dict[IndexKey, set[Entry]],
    terms: Iterable[str | None],
    owner: Entry | None = None,
) -> None:
    for term in terms:
        if not term:
            continue
        others = lookup(index, term) - ({owner} if owner else set())
        if others:
            raise ConflictError(f"'{term}' already refers to {_describe(others)}.")


def _unique_key(doc: TOMLDocument, index: dict[IndexKey, set[Entry]], base: str) -> str:
    candidate = base
    suffix = 2
    while (
        candidate in _users(doc)
        or candidate in _groups(doc)
        or lookup(index, candidate)
    ):
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _list_add(table: Any, name: str, value: str) -> None:
    if name in table:
        table[name].append(value)
    else:
        table[name] = [value]


def _list_remove(table: Any, name: str, matches: Callable[[str], bool]) -> int:
    values = table.get(name)
    if values is None:
        return 0
    positions = [position for position, item in enumerate(values) if matches(str(item))]
    for position in reversed(positions):
        del values[position]
    if not values:
        del table[name]
    return len(positions)


def _edit_list(table: Any, edit: _ListEdit, label: str) -> list[str]:
    notes: list[str] = []
    for value in edit.add:
        if any(
            alias_key(existing) == alias_key(value)
            for existing in _texts(table, edit.field)
        ):
            notes.append(f"'{value}' is already a {edit.noun} of {label}.")
            continue
        _list_add(table, edit.field, value)
        notes.append(f"Add {edit.noun} '{value}' to {label}.")
    for value in edit.remove:
        target = alias_key(value)
        if not _list_remove(
            table, edit.field, lambda item, target=target: alias_key(item) == target
        ):
            raise NameNotFoundError(f"'{value}' is not a {edit.noun} of {label}.")
        notes.append(f"Remove {edit.noun} '{value}' from {label}.")
    return notes


def _handle_logins(handles: Iterable[Handle]) -> list[str | None]:
    return [handle.user for handle in handles]


def _same_handle(left: str, right: str) -> bool:
    return handle_key(str(left)) == handle_key(str(right))


def _merge_service(table: Any, service: str) -> str:
    """Return the spelling of ``service`` in ``table``, merging its case variants.

    The first spelling keeps every handle, as a list; later variants are removed.
    """
    names = [name for name in table if name.casefold() == service]
    if not names:
        return service
    first = names[0]
    if len(names) == 1 and not isinstance(table[first], str):
        return first
    merged: list[str] = []
    for name in names:
        value = table[name]
        for login in [value] if isinstance(value, str) else value:
            if login and not any(_same_handle(login, seen) for seen in merged):
                merged.append(str(login))
    for name in names[1:]:
        del table[name]
    table[first] = merged
    return first


def _add_handles(user: Any, handles: list[Handle], label: str) -> list[str]:
    notes: list[str] = []
    for handle in handles:
        if _HANDLES not in user:
            user[_HANDLES] = tomlkit.table()
        table = user[_HANDLES]
        service = _merge_service(table, handle.service)
        if any(
            _same_handle(login, handle.user or "") for login in _texts(table, service)
        ):
            notes.append(f"'{handle.user}' is already a {service} handle of {label}.")
            continue
        _list_add(table, service, handle.user)
        notes.append(f"Add {service} handle '{handle.user}' to {label}.")
    return notes


def _remove_handles(user: Any, handles: list[Handle], label: str) -> list[str]:
    notes: list[str] = []
    table = user.get(_HANDLES, {})
    for handle in handles:
        service = _merge_service(table, handle.service)
        if service not in table:
            raise NameNotFoundError(f"{label} has no {handle.service} handle.")
        if handle.user is None:
            del table[service]
            notes.append(f"Remove every {service} handle from {label}.")
            continue
        target = handle.user
        if not _list_remove(
            table, service, lambda item, target=target: _same_handle(item, target)
        ):
            raise NameNotFoundError(
                f"'{handle.user}' is not a {service} handle of {label}."
            )
        notes.append(f"Remove {service} handle '{handle.user}' from {label}.")
    if _HANDLES in user and not user[_HANDLES]:
        del user[_HANDLES]
    return notes


def _require_valid_key(key: str) -> None:
    problem = key_error(key)
    if problem:
        raise MyGroupsError(f"Key '{key}': {problem}")


def _new_table(
    values: Mapping[str, str | list[str] | None], handles: Iterable[Handle] = ()
) -> Any:
    table = tomlkit.table()
    for name, value in values.items():
        if value:
            table[name] = value
    by_service: dict[str, list[str]] = {}
    for handle in handles:
        if handle.user:
            by_service.setdefault(handle.service, []).append(handle.user)
    if by_service:
        table[_HANDLES] = tomlkit.table()
        for service, logins in by_service.items():
            table[_HANDLES][service] = logins
    table.add(tomlkit.nl())
    return table


def add_user(doc: TOMLDocument, user: UserInput) -> list[str]:
    """Add a user; fails if the key, name, an alias, email, or handle is taken."""
    index = build_index(doc)
    user = replace(user, email=checked_email(user.email))
    key = user.key or slugify(user.aliases[0] if user.aliases else user.name)
    if not key:
        raise MyGroupsError(f"Cannot derive a key from '{user.name}'; pass --key.")
    _require_valid_key(key)
    if key in _users(doc) or key in _groups(doc):
        raise ConflictError(f"Key '{key}' is already taken; pass a different --key.")
    _ensure_terms_free(
        index,
        [key, user.name, user.email, *user.aliases, *_handle_logins(user.handles)],
    )
    values = {"name": user.name, "aliases": user.aliases, "email": user.email}
    _section(doc, "users")[key] = _new_table(values, user.handles)
    return [f"Add user {key} ({user.name})."]


def _pin_members_to_key(
    doc: TOMLDocument, index: dict[IndexKey, set[Entry]], key: str
) -> list[str]:
    """Rewrite group members that name user ``key`` another way to the key itself."""
    notes: list[str] = []
    for group_key, group in _groups(doc).items():
        members = group.get("members", [])
        for position, member in enumerate(members):
            text = str(member)
            if text != key and member_identity(index, text) == ("user", key):
                members[position] = key
                notes.append(f"Point member '{text}' of {group_key} at {key}.")
    return notes


def _pin_nested_to_key(
    doc: TOMLDocument, index: dict[IndexKey, set[Entry]], key: str
) -> list[str]:
    """Rewrite nested-group references that name group ``key`` another way to it."""
    notes: list[str] = []
    for group_key, group in _groups(doc).items():
        nested = group.get("groups", [])
        for position, item in enumerate(nested):
            text = str(item)
            if text != key and _nested_entry(index, text) == Entry("group", key):
                nested[position] = key
                notes.append(f"Point nested group '{text}' of {group_key} at {key}.")
    return notes


def _changes_lookup_names(update: UserUpdate) -> bool:
    return bool(
        update.name
        or update.email is not None
        or update.remove_aliases
        or update.remove_handles
    )


def update_user(doc: TOMLDocument, who: str, update: UserUpdate) -> list[str]:
    """Change a user's name, aliases, email, or handles."""
    update = replace(update, email=checked_email(update.email))
    index = build_index(doc)
    entry = _require(index, who, "user")
    table = _users(doc)[entry.key]
    _ensure_terms_free(
        index,
        [
            update.name,
            update.email,
            *update.add_aliases,
            *_handle_logins(update.add_handles),
        ],
        owner=entry,
    )
    notes: list[str] = []
    if _changes_lookup_names(update):
        notes.extend(_pin_members_to_key(doc, index, entry.key))
    if update.name:
        table["name"] = update.name
        notes.append(f"Set name of {entry.key} to '{update.name}'.")
    if update.email:
        table["email"] = update.email
        notes.append(f"Set email of {entry.key} to '{update.email}'.")
    elif update.email == "" and "email" in table:
        del table["email"]
        notes.append(f"Clear email of {entry.key}.")
    alias_edit = _ListEdit(
        "aliases", "alias", update.add_aliases, update.remove_aliases
    )
    notes.extend(_edit_list(table, alias_edit, entry.key))
    notes.extend(_add_handles(table, update.add_handles, entry.key))
    notes.extend(_remove_handles(table, update.remove_handles, entry.key))
    if not notes:
        raise MyGroupsError("Nothing to change; pass at least one option.")
    return notes


def _remove_member_everywhere(
    doc: TOMLDocument, index: dict[IndexKey, set[Entry]], identity: Identity
) -> list[str]:
    notes: list[str] = []
    for group_key, group in _groups(doc).items():
        removed = _list_remove(
            group, "members", lambda item: member_identity(index, item) == identity
        )
        if removed:
            notes.append(f"Remove {identity[1]} from group {group_key}.")
    return notes


def remove_user(doc: TOMLDocument, who: str) -> list[str]:
    """Remove a user and take them out of every group that lists them."""
    index = build_index(doc)
    entry = _require(index, who, "user")
    notes = [f"Remove user {entry.key}."]
    notes.extend(_remove_member_everywhere(doc, index, ("user", entry.key)))
    del _users(doc)[entry.key]
    return notes


def _prepare_member(
    doc: TOMLDocument, member: str, existing: set[Identity], group_key: str
) -> tuple[str | None, str]:
    """Return ``(value to store or None, note)``; unknown names become stub users."""
    index = build_index(doc)
    identity = member_identity(index, member)
    kind, value = identity
    prefix, bare = split_kind(member)
    if kind == "email" and prefix:
        raise NameNotFoundError(
            f"No user has the email '{bare}'; pass the bare address to add it "
            "without a user entry."
        )
    if identity in existing:
        return None, f"'{member}' is already a member of {group_key}."
    existing.add(identity)
    if kind == "user":
        return value, f"Add {value} to {group_key}."
    if kind == "email":
        address = parse_email(bare) or bare.strip()
        return address, f"Add {address} to {group_key} (no user entry yet)."
    found = find_entry(index, member)
    if found is not None and found.kind == "group":
        raise ConflictError(f"'{member}' is {found}; nest it with --include instead.")
    name = bare.strip()
    key = _unique_key(doc, index, slugify(name) or "user")
    _section(doc, "users")[key] = _new_table({"name": name})
    existing.add(("user", key))
    note = f"Create user {key} with only a name ('{name}') and add them to {group_key}."
    return key, note + _hint(index, member)


def add_group(doc: TOMLDocument, group: GroupInput) -> list[str]:
    """Add a group; members are keys, aliases, or emails, and new names become stubs."""
    if not group.members and not group.includes:
        raise MyGroupsError("A new group needs at least one --member or --include.")
    index = build_index(doc)
    key = group.key or slugify(group.name)
    if not key:
        raise MyGroupsError(f"Cannot derive a key from '{group.name}'; pass --key.")
    _require_valid_key(key)
    if key in _users(doc) or key in _groups(doc):
        raise ConflictError(f"Key '{key}' is already taken; pass a different --key.")
    aliases = [alias for alias in group.aliases if alias_key(alias) != alias_key(key)]
    if alias_key(group.name) != alias_key(key):
        aliases.insert(0, group.name)
    _ensure_terms_free(index, [key, *aliases])
    nested = [_require(index, include, "group").key for include in group.includes]
    notes = [f"Add group {key}."]
    stored: list[str] = []
    existing: set[Identity] = set()
    for member in group.members:
        value, note = _prepare_member(doc, member, existing, key)
        notes.append(note)
        if value is not None:
            stored.append(value)
    notes.extend(f"Include group {nested_key} in {key}." for nested_key in nested)
    _section(doc, "groups")[key] = _new_table(
        {"aliases": aliases, "members": stored, "groups": nested}
    )
    return notes


def add_group_members(doc: TOMLDocument, group: str, members: list[str]) -> list[str]:
    """Add members to a group, skipping ones already listed."""
    index = build_index(doc)
    entry = _require(index, group, "group")
    table = _groups(doc)[entry.key]
    existing = {member_identity(index, member) for member in _texts(table, "members")}
    notes: list[str] = []
    for member in members:
        value, note = _prepare_member(doc, member, existing, entry.key)
        notes.append(note)
        if value is not None:
            _list_add(table, "members", value)
    return notes


def remove_group_members(
    doc: TOMLDocument, group: str, members: list[str]
) -> list[str]:
    """Remove direct members from a group. User entries are kept."""
    index = build_index(doc)
    entry = _require(index, group, "group")
    table = _groups(doc)[entry.key]
    notes: list[str] = []
    for member in members:
        identity = member_identity(index, member)
        if not _list_remove(
            table,
            "members",
            lambda item, identity=identity: member_identity(index, item) == identity,
        ):
            raise NameNotFoundError(
                f"'{member}' is not a direct member of {entry.key}."
            )
        notes.append(f"Remove {member} from {entry.key}.")
    return notes


def _include_group(
    doc: TOMLDocument, index: dict[IndexKey, set[Entry]], key: str, include: str
) -> str:
    nested = _require(index, include, "group").key
    if nested == key:
        raise ConflictError(f"Group {key} cannot include itself.")
    if any(
        find_entry(index, item, kind="group") == Entry("group", nested)
        for item in _texts(_groups(doc)[key], "groups")
    ):
        return f"{key} already includes {nested}."
    _list_add(_groups(doc)[key], "groups", nested)
    expand_group(doc, index, key)
    return f"Include group {nested} in {key}."


def update_group(doc: TOMLDocument, group: str, update: GroupUpdate) -> list[str]:
    """Change a group's aliases and nested groups."""
    index = build_index(doc)
    entry = _require(index, group, "group")
    table = _groups(doc)[entry.key]
    _ensure_terms_free(index, list(update.add_aliases), owner=entry)
    alias_edit = _ListEdit(
        "aliases", "alias", update.add_aliases, update.remove_aliases
    )
    notes = _pin_nested_to_key(doc, index, entry.key) if update.remove_aliases else []
    notes.extend(_edit_list(table, alias_edit, entry.key))
    notes.extend(
        _include_group(doc, index, entry.key, include) for include in update.includes
    )
    for exclude in update.excludes:
        target = _require(index, exclude, "group")
        if not _list_remove(
            table,
            "groups",
            lambda item, target=target: find_entry(index, item, kind="group") == target,
        ):
            raise NameNotFoundError(f"{entry.key} does not include group {target.key}.")
        notes.append(f"Stop including group {target.key} in {entry.key}.")
    if not notes:
        raise MyGroupsError("Nothing to change; pass at least one option.")
    return notes


def remove_group(doc: TOMLDocument, group: str) -> list[str]:
    """Remove a group and every reference to it from other groups. Users are kept."""
    index = build_index(doc)
    entry = _require(index, group, "group")
    notes = [f"Remove group {entry.key}."]
    for other_key, other in _groups(doc).items():
        if other_key == entry.key:
            continue
        if _list_remove(
            other, "groups", lambda item: find_entry(index, item, kind="group") == entry
        ):
            notes.append(f"Stop including {entry.key} in {other_key}.")
    del _groups(doc)[entry.key]
    return notes


# === Writing ===


def _render(doc: TOMLDocument) -> str:
    # tomlkit separates a newly created top-level section from the table before it even
    # when that table already ends in a blank line; keep one blank line per header.
    # The pattern can also match inside a multiline string, so keep the cleanup only
    # if every value survives it.
    text = doc.as_string()
    cleaned = re.sub(r"\n{3,}(?=\[)", "\n\n", text).rstrip("\n") + "\n"
    if tomlkit.parse(cleaned).unwrap() == doc.unwrap():
        return cleaned
    return text


def _read_current(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def _lock_file(handle: Any) -> None:
    """Lock ``handle`` exclusively without waiting; raise ``OSError`` if it's held."""
    if fcntl is not None:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return
    # msvcrt locks bytes from the current position; byte 0 may lie past EOF.
    handle.seek(0)
    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)


def _unlock_file(handle: Any) -> None:
    if fcntl is not None:
        fcntl.flock(handle, fcntl.LOCK_UN)
        return
    handle.seek(0)
    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


@contextmanager
def _write_lock(path: Path) -> Iterator[None]:
    """Hold an exclusive lock on ``<name>.lock`` so two writers can't interleave."""
    if fcntl is None and msvcrt is None:
        raise ConflictError("This platform has no file locking; refusing to write.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(f"{path.name}.lock").open("a", encoding="utf-8") as handle:
        try:
            _lock_file(handle)
        except OSError as exc:
            raise ConflictError(
                f"Another write to {path} is in progress; try again after it ends."
            ) from exc
        try:
            yield
        finally:
            _unlock_file(handle)


def _print_plan(path: Path, notes: list[str], before: str | None, after: str) -> None:
    print(f"Planned changes to {path}:")
    for note in notes:
        print(f"  - {note}")
    diff = difflib.unified_diff(
        (before or "").splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"{path} (current)",
        tofile=f"{path} (planned)",
    )
    print()
    sys.stdout.writelines(diff)


def confirm_or_abort(path: Path, options: WriteOptions) -> None:
    """Require consent before a real write; ``--yes`` or ``--dry-run`` skips it."""
    if options.yes or options.dry_run:
        return
    if not sys.stdin.isatty():
        raise MyGroupsError(
            "Refusing to write without a terminal to confirm; re-run with --yes."
        )
    sys.stderr.write(f"\nWrite these changes to {path}? [y/N] ")
    sys.stderr.flush()
    try:
        answer = input()
    except EOFError:
        answer = ""
    if answer.strip().casefold() not in _YES_ANSWERS:
        raise AbortedError("Aborted; nothing written.")


def _write_target(path: Path) -> Path:
    """Return the file a write replaces: a symlink's target, so the link survives."""
    return path.resolve() if path.is_symlink() else path


def write_config(path: Path, text: str) -> Path | None:
    """Atomically replace ``path`` with ``text``, keeping a ``<name>.bak`` copy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        backup = path.with_name(f"{path.name}.bak")
        shutil.copy2(path, backup)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    try:
        os.replace(temp_path, path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise
    return backup


def _commit(
    path: Path,
    notes: list[str],
    before: str | None,
    after: str,
    options: WriteOptions,
) -> int:
    """Show the plan, confirm, and write ``after`` if the file still holds ``before``.

    ``before`` is ``None`` when the file did not exist when the plan was made.
    """
    _print_plan(path, notes, before, after)
    if options.dry_run:
        print("\nDry run: nothing written.")
        return 0
    confirm_or_abort(path, options)
    if _read_current(path) != before:
        raise ConflictError(
            f"{path} changed after this plan was made; nothing written. Run the "
            "command again to plan against the current file."
        )
    backup = write_config(path, after)
    suffix = f" (previous version saved to {backup})" if backup else ""
    print(f"\nWrote {path}{suffix}.")
    return 0


def _lock_unless_dry_run(path: Path, options: WriteOptions) -> AbstractContextManager:
    return nullcontext() if options.dry_run else _write_lock(path)


def _reject_new_errors(doc: TOMLDocument, existing: set[str]) -> None:
    new_errors = [error for error in validate(doc)[0] if error not in existing]
    if new_errors:
        raise ConflictError(
            "Nothing written; the change would leave the file inconsistent:\n  "
            + "\n  ".join(new_errors)
        )


def apply_change(options: WriteOptions, mutate: Mutation) -> int:
    """Load the file, apply ``mutate``, show the plan, and write unless dry-running.

    The change is refused if it introduces a ``validate`` error, such as a name that
    now refers to two entries.
    """
    path = _write_target(get_config_path())
    with _lock_unless_dry_run(path, options):
        before = _read_current(path)
        doc = load_document(path, missing_ok=True)
        existing_errors = set(validate(doc)[0])
        notes = mutate(doc)
        _reject_new_errors(doc, existing_errors)
        if before is not None and doc.as_string() == before:
            for note in notes:
                print(note)
            print("No changes.")
            return 0
        return _commit(path, notes, before, _render(doc), options)


# === Command handlers ===


def _write_options(args: argparse.Namespace) -> WriteOptions:
    return WriteOptions(dry_run=args.dry_run, yes=args.yes)


def _handle_path(_args: argparse.Namespace) -> int:
    print(get_config_path())
    return 0


def _handles_text(user: Any) -> str:
    return "; ".join(
        f"{service}: {', '.join(logins)}" for service, logins in _handles(user).items()
    )


def _user_line(key: str, user: Any) -> str:
    parts = [key, _text(user, "name")]
    aliases = _texts(user, "aliases")
    if aliases:
        parts.append(f"aliases: {', '.join(aliases)}")
    if _text(user, "email"):
        parts.append(f"email: {_text(user, 'email')}")
    if _handles(user):
        parts.append(_handles_text(user))
    return "  " + " | ".join(parts)


def _group_line(doc: TOMLDocument, index: dict[IndexKey, set[Entry]], key: str) -> str:
    group = _groups(doc)[key]
    aliases = _texts(group, "aliases")
    try:
        members, unresolved = _collect(doc, index, expand_group(doc, index, key))
        count = f"{len(members) + len(unresolved)} members"
    except MyGroupsError:
        count = "invalid; run validate"
    alias_text = f" | aliases: {', '.join(aliases)}" if aliases else ""
    return f"  {key}{alias_text} | {count}"


def _handle_list(_args: argparse.Namespace) -> int:
    doc = load_document(get_config_path())
    index = build_index(doc)
    users = _users(doc)
    groups = _groups(doc)
    print(f"Users ({len(users)}):")
    for key, user in users.items():
        print(_user_line(key, user))
    print(f"Groups ({len(groups)}):")
    for key in groups:
        print(_group_line(doc, index, key))
    return 0


def _groups_containing(
    doc: TOMLDocument, index: dict[IndexKey, set[Entry]], identity: Identity
) -> list[str]:
    found = []
    for key in _groups(doc):
        try:
            members = expand_group(doc, index, key)
        except MyGroupsError:
            continue
        if any(member_identity(index, member) == identity for member in members):
            found.append(key)
    return found


def _show_group(doc: TOMLDocument, index: dict[IndexKey, set[Entry]], key: str) -> None:
    group = _groups(doc)[key]
    print(Entry("group", key))
    for name in ("aliases", "groups"):
        if _texts(group, name):
            print(f"  {name}: {', '.join(_texts(group, name))}")
    members, unresolved = _collect(doc, index, expand_group(doc, index, key))
    print(f"  members ({len(members) + len(unresolved)}):")
    for member in members:
        label = member["key"] or member["email"]
        detail = " ".join(
            part
            for part in (
                member["name"],
                f"<{member['email']}>" if member["email"] else "",
            )
            if part
        )
        print(f"    {label}  {detail}".rstrip())
    for name in unresolved:
        print(f"    {name}  (unresolved)")


def _show_user(doc: TOMLDocument, index: dict[IndexKey, set[Entry]], key: str) -> None:
    user = _users(doc)[key]
    print(Entry("user", key))
    for name, value in user.items():
        if name == _HANDLES:
            continue
        shown = (
            ", ".join(str(item) for item in value) if isinstance(value, list) else value
        )
        print(f"  {name}: {shown}")
    for service, logins in _handles(user).items():
        print(f"  {service}: {', '.join(logins)}")
    containing = _groups_containing(doc, index, ("user", key))
    print(f"  groups: {', '.join(containing) if containing else '(none)'}")


def _handle_show(args: argparse.Namespace) -> int:
    doc = load_document(get_config_path())
    index = build_index(doc)
    entry = find_entry(index, args.name)
    if entry is None:
        raise NameNotFoundError(
            f"No user or group named '{args.name}'.{_hint(index, args.name)}"
        )
    if entry.kind == "group":
        _show_group(doc, index, entry.key)
    else:
        _show_user(doc, index, entry.key)
    return 0


def _member_values(member: dict[str, Any], args: argparse.Namespace) -> list[str]:
    if args.email:
        return [member["email"]] if member["email"] else []
    return member["handles"].get(args.handle.casefold(), [])


def _print_lines(result: dict[str, Any], args: argparse.Namespace) -> int:
    """Print each member's values, one per line; return how many members had none."""
    wanted = "email" if args.email else f"{args.handle} handle"
    end = "\0" if args.null else "\n"
    missing = 0
    for member in result["members"]:
        values = _member_values(member, args)
        for value in values:
            sys.stdout.write(value + end)
        if not values:
            missing += 1
            label = member["name"] or member["key"] or member["email"]
            print(f"warning: no {wanted} for {label}", file=sys.stderr)
    return missing


def _handle_resolve(args: argparse.Namespace) -> int:
    doc = load_document(get_config_path())
    result = resolve(doc, args.names)
    missing = 0
    if args.email or args.handle:
        missing = _print_lines(result, args)
    else:
        print(json.dumps(to_jscontact(doc, result), indent=2, ensure_ascii=False))
    for name in result["unresolved"]:
        print(f"warning: unresolved name '{name}'", file=sys.stderr)
    incomplete = missing or result["unresolved"]
    return EXIT_INCOMPLETE if args.strict and incomplete else 0


def _handle_validate(_args: argparse.Namespace) -> int:
    path = get_config_path()
    doc = load_document(path)
    errors, warnings = validate(doc)
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"OK: {len(_users(doc))} users, {len(_groups(doc))} groups in {path}.")
    return 0


def _handle_init(args: argparse.Namespace) -> int:
    path = _write_target(get_config_path())
    options = _write_options(args)
    with _lock_unless_dry_run(path, options):
        if path.exists():
            raise ConflictError(f"{path} already exists; init never overwrites it.")
        text = _EXAMPLE_PATH.read_text(encoding="utf-8")
        return _commit(
            path, ["Create the file from the example template."], None, text, options
        )


def _handle_user_add(args: argparse.Namespace) -> int:
    user = UserInput(
        name=args.name,
        aliases=args.alias,
        email=args.email,
        handles=args.handle,
        key=args.key,
    )
    return apply_change(_write_options(args), lambda doc: add_user(doc, user))


def _handle_user_update(args: argparse.Namespace) -> int:
    update = UserUpdate(
        name=args.name,
        add_aliases=args.add_alias,
        remove_aliases=args.remove_alias,
        email=args.email,
        add_handles=args.add_handle,
        remove_handles=args.remove_handle,
    )
    return apply_change(
        _write_options(args), lambda doc: update_user(doc, args.who, update)
    )


def _handle_user_remove(args: argparse.Namespace) -> int:
    return apply_change(_write_options(args), lambda doc: remove_user(doc, args.who))


def _handle_group_add(args: argparse.Namespace) -> int:
    group = GroupInput(
        name=args.name,
        aliases=args.alias,
        members=args.member,
        includes=args.include,
        key=args.key,
    )
    return apply_change(_write_options(args), lambda doc: add_group(doc, group))


def _handle_group_update(args: argparse.Namespace) -> int:
    update = GroupUpdate(
        add_aliases=args.add_alias,
        remove_aliases=args.remove_alias,
        includes=args.include,
        excludes=args.exclude,
    )
    return apply_change(
        _write_options(args), lambda doc: update_group(doc, args.group, update)
    )


def _handle_group_add_member(args: argparse.Namespace) -> int:
    return apply_change(
        _write_options(args),
        lambda doc: add_group_members(doc, args.group, args.members),
    )


def _handle_group_remove_member(args: argparse.Namespace) -> int:
    return apply_change(
        _write_options(args),
        lambda doc: remove_group_members(doc, args.group, args.members),
    )


def _handle_group_remove(args: argparse.Namespace) -> int:
    return apply_change(_write_options(args), lambda doc: remove_group(doc, args.group))


# === Argument parsing ===


def _parse_handle(text: str, *, user_required: bool) -> Handle:
    service, sep, user = text.partition("=")
    handle = Handle(service.strip().casefold(), user.strip() or None)
    if not handle.service or (handle.user is None and (sep or user_required)):
        raise argparse.ArgumentTypeError(
            f"expected SERVICE=USER, e.g. github=octocat; got '{text}'"
        )
    return handle


def _handle_arg(text: str) -> Handle:
    return _parse_handle(text, user_required=True)


def _handle_ref_arg(text: str) -> Handle:
    return _parse_handle(text, user_required=False)


def _write_parent() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the planned change without writing it.",
    )
    parent.add_argument(
        "--yes", "-y", action="store_true", help="Skip the confirmation prompt."
    )
    return parent


def _add_user_commands(subparsers: Any, write_parent: argparse.ArgumentParser) -> None:
    user = subparsers.add_parser("user", help="Add, update, or remove a user.")
    commands = user.add_subparsers(dest="user_command", required=True)

    add = commands.add_parser("add", parents=[write_parent], help="Add a user.")
    add.add_argument("name", help="Display name, e.g. 'Ada Lovelace'.")
    add.add_argument(
        "--key", help="Table key; defaults to a slug of the first alias or the name."
    )
    add.add_argument(
        "--alias", action="append", default=[], help="Nickname or shortcut; repeatable."
    )
    add.add_argument("--email", help="Email address.")
    add.add_argument(
        "--handle",
        action="append",
        default=[],
        type=_handle_arg,
        metavar="SERVICE=USER",
        help="Username on a service, e.g. github=octocat; repeatable.",
    )
    add.set_defaults(handler=_handle_user_add)

    update = commands.add_parser(
        "update", parents=[write_parent], help="Change a user."
    )
    update.add_argument("who", help="Key, alias, name, email, or handle of the user.")
    update.add_argument("--name", help="New display name.")
    update.add_argument(
        "--add-alias", action="append", default=[], help="Alias to add; repeatable."
    )
    update.add_argument(
        "--remove-alias",
        action="append",
        default=[],
        help="Alias to remove; repeatable.",
    )
    update.add_argument("--email", help='Email address. Pass "" to clear it.')
    update.add_argument(
        "--add-handle",
        action="append",
        default=[],
        type=_handle_arg,
        metavar="SERVICE=USER",
        help="Handle to add, e.g. github=octocat; repeatable.",
    )
    update.add_argument(
        "--remove-handle",
        action="append",
        default=[],
        type=_handle_ref_arg,
        metavar="SERVICE[=USER]",
        help="Handle to remove, or SERVICE alone to remove all of them; repeatable.",
    )
    update.set_defaults(handler=_handle_user_update)

    remove = commands.add_parser(
        "remove",
        parents=[write_parent],
        help="Remove a user from the file and all groups.",
    )
    remove.add_argument("who", help="Key, alias, name, email, or handle of the user.")
    remove.set_defaults(handler=_handle_user_remove)


def _add_group_commands(subparsers: Any, write_parent: argparse.ArgumentParser) -> None:
    group = subparsers.add_parser(
        "group", help="Add, update, or remove a group and its members."
    )
    commands = group.add_subparsers(dest="group_command", required=True)

    add = commands.add_parser("add", parents=[write_parent], help="Add a group.")
    add.add_argument("name", help="Group name, e.g. 'platform team'.")
    add.add_argument("--key", help="Table key; defaults to a slug of the name.")
    add.add_argument(
        "--alias",
        action="append",
        default=[],
        help="Other name, e.g. 'my pod'; repeatable.",
    )
    add.add_argument(
        "--member",
        action="append",
        default=[],
        help="User key, alias, name, or email; repeatable.",
    )
    add.add_argument(
        "--include",
        action="append",
        default=[],
        help="Group to nest inside this one; repeatable.",
    )
    add.set_defaults(handler=_handle_group_add)

    update = commands.add_parser(
        "update", parents=[write_parent], help="Change a group's aliases or nesting."
    )
    update.add_argument("group", help="Key or alias of the group.")
    update.add_argument(
        "--add-alias", action="append", default=[], help="Alias to add; repeatable."
    )
    update.add_argument(
        "--remove-alias",
        action="append",
        default=[],
        help="Alias to remove; repeatable.",
    )
    update.add_argument(
        "--include", action="append", default=[], help="Group to nest; repeatable."
    )
    update.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Nested group to drop; repeatable.",
    )
    update.set_defaults(handler=_handle_group_update)

    add_member = commands.add_parser(
        "add-member", parents=[write_parent], help="Add members to a group."
    )
    add_member.add_argument("group", help="Key or alias of the group.")
    add_member.add_argument(
        "members", nargs="+", help="User keys, aliases, names, or emails."
    )
    add_member.set_defaults(handler=_handle_group_add_member)

    remove_member = commands.add_parser(
        "remove-member", parents=[write_parent], help="Remove members from a group."
    )
    remove_member.add_argument("group", help="Key or alias of the group.")
    remove_member.add_argument(
        "members", nargs="+", help="User keys, aliases, names, or emails."
    )
    remove_member.set_defaults(handler=_handle_group_remove_member)

    remove = commands.add_parser(
        "remove", parents=[write_parent], help="Remove a group; users are kept."
    )
    remove.add_argument("group", help="Key or alias of the group.")
    remove.set_defaults(handler=_handle_group_remove)


def _add_resolve_command(subparsers: Any) -> None:
    resolve_parser = subparsers.add_parser(
        "resolve",
        help="Resolve groups or users to JSContact (RFC 9553) JSON, or to one email "
        "or handle per line.",
    )
    resolve_parser.add_argument(
        "names", nargs="+", help="Group or user names, e.g. 'my pod' Ada group:pod."
    )
    output = resolve_parser.add_mutually_exclusive_group()
    output.add_argument(
        "--email", action="store_true", help="Print one email per line instead."
    )
    output.add_argument(
        "--handle",
        metavar="SERVICE",
        help="Print each member's SERVICE handles, one per line, instead.",
    )
    resolve_parser.add_argument(
        "-0",
        "--null",
        action="store_true",
        help="With --email or --handle, end each value with NUL, for xargs -0.",
    )
    resolve_parser.add_argument(
        "--strict",
        action="store_true",
        help=f"Exit {EXIT_INCOMPLETE} if a name is unresolved or a member lacks the "
        "requested email or handle.",
    )
    resolve_parser.set_defaults(handler=_handle_resolve)


def build_parser() -> argparse.ArgumentParser:
    """Build the ``my_groups.py`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="my_groups.py", description=__doc__.splitlines()[0]
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    write_parent = _write_parent()

    subparsers.add_parser("path", help="Print the groups file path.").set_defaults(
        handler=_handle_path
    )
    subparsers.add_parser("list", help="List users and groups.").set_defaults(
        handler=_handle_list
    )
    show = subparsers.add_parser("show", help="Show one user or group.")
    show.add_argument("name", help="Key, alias, name, email, or handle.")
    show.set_defaults(handler=_handle_show)
    _add_resolve_command(subparsers)
    subparsers.add_parser("validate", help="Check the file for problems.").set_defaults(
        handler=_handle_validate
    )
    init = subparsers.add_parser(
        "init",
        parents=[write_parent],
        help="Create the file from the example template.",
    )
    init.set_defaults(handler=_handle_init)

    _add_user_commands(subparsers, write_parent)
    _add_group_commands(subparsers, write_parent)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return its exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "null", False) and not (args.email or args.handle):
        parser.error("--null needs --email or --handle.")
    try:
        return args.handler(args)
    except MyGroupsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
