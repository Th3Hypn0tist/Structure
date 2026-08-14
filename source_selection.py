from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from source_adapter import load_snapshot
from structureprojector import ProjectorError, SOURCE_REPO, SourceSnapshot

# app.py historically calls ProjectorError.to_dict(); the base class exposes
# as_dict(). Keep both spellings compatible while source selection is active.
if not hasattr(ProjectorError, "to_dict") and hasattr(ProjectorError, "as_dict"):
    ProjectorError.to_dict = ProjectorError.as_dict

SOURCE_GITHUB = "github"
SOURCE_DIRECTORY = "directory"


def normalize_source_spec(spec: dict[str, Any] | None) -> dict[str, str]:
    raw = spec if isinstance(spec, dict) else {}
    source_type = str(raw.get("type") or SOURCE_GITHUB).strip().lower()
    if source_type == SOURCE_GITHUB:
        return {
            "type": SOURCE_GITHUB,
            "repo": str(raw.get("repo") or SOURCE_REPO).strip(),
            "branch": str(raw.get("branch") or "main").strip(),
        }
    if source_type == SOURCE_DIRECTORY:
        path = str(raw.get("path") or "").strip()
        if not path:
            raise ProjectorError("SP_SOURCE_DIRECTORY_REQUIRED", "Local directory source requires a path")
        return {"type": SOURCE_DIRECTORY, "path": path}
    raise ProjectorError("SP_SOURCE_TYPE", f"Unsupported source type: {source_type!r}")


def load_directory_snapshot(path: str) -> SourceSnapshot:
    root = Path(path).expanduser()
    try:
        root = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ProjectorError("SP_SOURCE_DIRECTORY_INVALID", f"Unable to resolve local directory: {path!r}") from exc
    if not root.is_dir():
        raise ProjectorError("SP_SOURCE_DIRECTORY_INVALID", f"Local source is not a directory: {str(root)!r}")

    files: dict[str, bytes] = {}
    digest = hashlib.sha256()

    try:
        for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            dirs[:] = sorted(
                name for name in dirs
                if name != ".git" and not (current_path / name).is_symlink()
            )
            for name in sorted(names):
                absolute = current_path / name
                if absolute.is_symlink() or not absolute.is_file():
                    continue
                relative = absolute.relative_to(root).as_posix()
                payload = absolute.read_bytes()
                files[relative] = payload
                encoded = relative.encode("utf-8")
                digest.update(len(encoded).to_bytes(8, "big"))
                digest.update(encoded)
                digest.update(len(payload).to_bytes(8, "big"))
                digest.update(payload)
    except (OSError, PermissionError) as exc:
        raise ProjectorError("SP_SOURCE_DIRECTORY_READ", f"Unable to read local directory source: {str(root)!r}") from exc

    return SourceSnapshot(
        repo=f"directory:{root}",
        branch="local",
        revision=digest.hexdigest(),
        files=files,
    )


def load_source(spec: dict[str, Any] | None) -> SourceSnapshot:
    normalized = normalize_source_spec(spec)
    if normalized["type"] == SOURCE_DIRECTORY:
        return load_directory_snapshot(normalized["path"])
    return load_snapshot(branch=normalized["branch"], repo=normalized["repo"])


def source_spec_from_query(query: dict[str, list[str]]) -> dict[str, str]:
    source_type = (query.get("source_type") or [SOURCE_GITHUB])[0]
    if source_type == SOURCE_DIRECTORY:
        return {"type": SOURCE_DIRECTORY, "path": (query.get("source_path") or [""])[0]}
    return {
        "type": SOURCE_GITHUB,
        "repo": (query.get("repo") or [SOURCE_REPO])[0],
        "branch": (query.get("branch") or ["main"])[0],
    }


def source_summary(snapshot: SourceSnapshot) -> dict[str, Any]:
    source_type = SOURCE_DIRECTORY if str(snapshot.repo).startswith("directory:") else SOURCE_GITHUB
    return {
        "type": source_type,
        "repository": snapshot.repo,
        "branch": snapshot.branch,
        "revision": snapshot.revision,
        "files": len(snapshot.files),
    }
