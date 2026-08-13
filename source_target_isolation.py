from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

ERROR_ID = "STRUCTURE_SOURCE_TARGET_COLLISION"


class SourceTargetCollision(ValueError):
    def __init__(self, message: str = "Source and target must never be the same repository or directory.") -> None:
        super().__init__(message)
        self.id = ERROR_ID


def normalize_repository(locator: str | None) -> str | None:
    if not isinstance(locator, str) or not locator.strip():
        return None
    value = locator.strip()

    # git@host:owner/repo.git -> host/owner/repo
    ssh = re.fullmatch(r"git@([^:]+):(.+)", value)
    if ssh:
        host = ssh.group(1).lower()
        path = ssh.group(2)
    else:
        parsed = urlparse(value if "://" in value else f"https://{value}")
        host = (parsed.hostname or "").lower()
        path = parsed.path.lstrip("/")

    path = path.rstrip("/")
    if path.lower().endswith(".git"):
        path = path[:-4]
    if not host or not path:
        return value.casefold().rstrip("/")
    return f"{host}/{path}".casefold()


def normalize_directory(locator: str | os.PathLike[str] | None) -> str | None:
    if locator is None:
        return None
    value = os.fspath(locator).strip()
    if not value:
        return None
    return os.path.normcase(os.path.realpath(os.path.expanduser(value)))


def validate_source_target(
    *,
    source_repository: str | None = None,
    target_repository: str | None = None,
    source_directory: str | os.PathLike[str] | None = None,
    target_directory: str | os.PathLike[str] | None = None,
) -> None:
    """Fail closed when source and target are provably the same location.

    At least one locator must be supplied for each side. Repository equality and
    directory equality are independently fatal whenever both values of that
    locator type are available.
    """
    src_repo = normalize_repository(source_repository)
    dst_repo = normalize_repository(target_repository)
    src_dir = normalize_directory(source_directory)
    dst_dir = normalize_directory(target_directory)

    if not (src_repo or src_dir):
        raise ValueError("Source requires a repository or directory locator.")
    if not (dst_repo or dst_dir):
        raise ValueError("Target requires a repository or directory locator.")

    if src_repo and dst_repo and src_repo == dst_repo:
        raise SourceTargetCollision()
    if src_dir and dst_dir and src_dir == dst_dir:
        raise SourceTargetCollision()


def assert_distinct_locations(source: dict, target: dict) -> None:
    validate_source_target(
        source_repository=source.get("repository"),
        target_repository=target.get("repository"),
        source_directory=source.get("directory"),
        target_directory=target.get("directory"),
    )
