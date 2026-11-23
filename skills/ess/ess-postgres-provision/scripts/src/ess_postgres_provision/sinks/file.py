"""The default sink: a `0600` `.env` file in a `0700` data directory."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess  # nosec B404 -- runs git with a fixed argument list, no shell
from collections.abc import Sequence
from pathlib import Path

from ..exceptions import PreflightError
from .base import Outcome, RoleSecret, SinkContext, render_env

_TOOL_DIRECTORY = "ess-postgres-provision"
_PRIVATE_DIRECTORY_MODE = 0o700
_PRIVATE_FILE_MODE = 0o600
_GROUP_OR_OTHER_BITS = stat.S_IRWXG | stat.S_IRWXO
_GIT_TIMEOUT_SECONDS = 10
_MAX_SUFFIX = 100


def data_directory(host: str) -> Path:
    """`$XDG_DATA_HOME/ess-postgres-provision/<host>`, or under `~/.local/share`."""
    root = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(root) / _TOOL_DIRECTORY / _host_directory(host)


def _host_directory(host: str) -> str:
    if host.startswith("/"):
        return "socket-" + (host.strip("/").replace("/", "_") or "root")
    return host


def default_path(context: SinkContext) -> Path:
    """Where a run's file goes when `--sink-path` does not say otherwise.

    `rotated` and `failed` files carry a UTC timestamp, plus a counter when
    two runs land in the same second, so they never collide.
    """
    path = data_directory(context.host) / f"{context.base}.env"
    if context.outcome is Outcome.CREATED:
        return path
    return stamped_path(path, context)


def stamped_path(path: Path, context: SinkContext) -> Path:
    """`<stem>.<outcome>-<timestamp><suffix>` beside `path`, free of any file."""
    stamp = context.timestamp.strftime("%Y%m%dT%H%M%SZ")
    stem = f"{path.stem}.{context.outcome.value}-{stamp}"
    candidate = path.with_name(f"{stem}{path.suffix}")
    for counter in range(2, _MAX_SUFFIX):
        if not candidate.exists():
            break
        candidate = path.with_name(f"{stem}-{counter}{path.suffix}")
    return candidate


def display_path(path: Path) -> str:
    """The path with the home directory shortened to `~`."""
    home = Path.home()
    return f"~/{path.relative_to(home)}" if path.is_relative_to(home) else str(path)


class FileSink:
    """Writes credentials to a new file, never overwriting one.

    A failed run always writes to a timestamped `failed` file, beside the
    chosen path or in the data directory, so a later `create` is not blocked
    by a half-finished run's file.
    """

    name = "file"

    def __init__(self, context: SinkContext) -> None:
        self.context = context
        self._private_directory: Path | None = None
        self._unstamped: Path | None = None
        if context.path is None:
            self._private_directory = data_directory(context.host)
            if context.outcome is not Outcome.CREATED:
                self._unstamped = self._private_directory / f"{context.base}.env"
            self.path = default_path(context)
        elif context.outcome is Outcome.FAILED:
            self._unstamped = context.path.expanduser()
            self.path = stamped_path(self._unstamped, context)
        else:
            self.path = context.path.expanduser()

    def check(self) -> None:
        """Refuse an existing file, a shared directory, or an untracked git path.

        A timestamped path that another run took after an earlier check first
        moves to the next free counter.

        Raises:
            PreflightError: The file cannot be created safely.
        """
        if self._unstamped is not None and self.path.exists():
            self.path = stamped_path(self._unstamped, self.context)
        if self.path.exists():
            msg = (
                f"{display_path(self.path)} already exists and is never overwritten. "
                "Move it aside, or pass --sink-path."
            )
            raise PreflightError(msg)
        self._check_directory()
        self._check_git_ignored()

    def deliver(self, secrets: Sequence[RoleSecret]) -> str:
        """Create the file with `O_EXCL` and mode `0600`, then write it."""
        self._make_parent()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(self.path, flags, _PRIVATE_FILE_MODE)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(render_env(self.context, secrets))
            handle.flush()
            os.fsync(handle.fileno())
        return f"Credentials written to {display_path(self.path)}"

    def _check_directory(self) -> None:
        if self._private_directory is not None and self._private_directory.exists():
            mode = self._private_directory.stat().st_mode
            if mode & _GROUP_OR_OTHER_BITS:
                msg = (
                    f"{display_path(self._private_directory)} is accessible to other "
                    f"users. Run `chmod 700 {self._private_directory}` and retry."
                )
                raise PreflightError(msg)
        ancestor = _nearest_existing(self.path.parent)
        if not ancestor.is_dir() or not os.access(ancestor, os.W_OK | os.X_OK):
            msg = (
                f"Cannot create {display_path(self.path)}: {ancestor} is not writable."
            )
            raise PreflightError(msg)

    def _check_git_ignored(self) -> None:
        git = shutil.which("git")
        if git is None:
            return
        ancestor = _nearest_existing(self.path.parent)
        inside = subprocess.run(  # nosec B603 -- fixed git arguments, no shell
            [git, "-C", str(ancestor), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return
        # `-C ancestor` changes git's cwd, so a relative path would be resolved twice.
        ignored = subprocess.run(  # nosec B603 -- fixed git arguments, no shell
            [
                git,
                "-C",
                str(ancestor),
                "check-ignore",
                "--quiet",
                str(self.path.resolve()),
            ],
            capture_output=True,
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
        if ignored.returncode != 0:
            msg = (
                f"{display_path(self.path)} is inside a git work tree and is not "
                "ignored. Add it to .gitignore, or choose a path outside the repo."
            )
            raise PreflightError(msg)

    def _make_parent(self) -> None:
        parent = self.path.parent
        missing = [parent, *parent.parents]
        missing = [directory for directory in missing if not directory.exists()]
        parent.mkdir(mode=_PRIVATE_DIRECTORY_MODE, parents=True, exist_ok=True)
        for directory in missing:
            directory.chmod(_PRIVATE_DIRECTORY_MODE)
        if self._private_directory is not None:
            self._private_directory.chmod(_PRIVATE_DIRECTORY_MODE)


def _nearest_existing(path: Path) -> Path:
    for candidate in (path, *path.parents):
        if candidate.exists():
            return candidate
    return Path("/")
