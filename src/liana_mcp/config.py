"""Operator-owned configuration. MCP arguments cannot select paths or networks."""

import hashlib
import os
import stat
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .errors import SafetyError


def private_directory(path: Path, *, create: bool = False) -> Path:
    if not path.is_absolute() or path != path.resolve():
        raise SafetyError("Use an absolute directory without symlink components.")
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        info = path.lstat()
    except OSError as error:
        raise SafetyError("The private state directory is unavailable.") from error
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise SafetyError("The state directory must belong to this user and have mode 0700.")
    return path


def private_file(path: Path) -> bytes:
    flags = os.O_RDONLY | os.O_NOFOLLOW
    try:
        with os.fdopen(os.open(path, flags), "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise SafetyError("A private regular file with mode 0600 is required.")
            data = stream.read(1_048_577)
            if len(data) > 1_048_576:
                raise SafetyError("The local state file is too large.")
            return data
    except OSError as error:
        raise SafetyError("The private local file is unavailable.") from error


class PinnedBinary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    def checked(self) -> Path:
        path = Path(self.path)
        if not path.is_absolute() or path != path.resolve() or not path.is_file():
            raise SafetyError(
                "A pinned executable must be a regular absolute path without symlinks."
            )
        info = path.stat()
        if info.st_mode & 0o022 or info.st_uid not in (0, os.getuid()):
            raise SafetyError("An executable is writable by another user.")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != self.sha256 or not os.access(path, os.X_OK):
            raise SafetyError("A local executable failed its pinned integrity check.")
        return path


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    state_directory: str
    core: PinnedBinary
    lianad: PinnedBinary
    gui: PinnedBinary | None = None
    language: str = Field(default="en", pattern=r"^(de|en)$")
    enable_regtest_mutations: bool = False
    require_operator_approval: bool = False

    @classmethod
    def load(cls, path: Path) -> "Settings":
        if os.geteuid() == 0:
            raise SafetyError("Do not run this experimental server as root.")
        try:
            return cls.model_validate(tomllib.loads(private_file(path).decode()))
        except (ValueError, UnicodeError, ValidationError) as error:
            raise SafetyError("Invalid operator configuration.") from error
