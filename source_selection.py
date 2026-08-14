from __future__ import annotations

import hashlib
import os
import re
import string
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from source_adapter import load_snapshot
from structureprojector import ProjectorError, SOURCE_REPO, SourceSnapshot

if not hasattr(ProjectorError, "to_dict") and hasattr(ProjectorError, "as_dict"):
    ProjectorError.to_dict = ProjectorError.as_dict

SOURCE_GITHUB = "github"
SOURCE_DIRECTORY = "directory"
CANONICAL_BOOTSTRAP = "00_Contract_Format.json"
_WINDOWS_DRIVE_PATH = re.compile(r"^([A-Za-z]):[\\/](.*)$")
_WINDOWS_FILE_URL_PATH = re.compile(r"^/([A-Za-z]):/(.*)$")


def _is_wsl() -> bool:
    if os.name == "nt":
        return False
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False


def _strip_wrapping_quotes(value: str) -> str:
    path = str(value or "").strip()
    if len(path) >= 2 and path[0] == path[-1] and path[0] in {"'", '"'}:
        return path[1:-1].strip()
    return path


def _decode_file_url(value: str) -> str:
    path = _strip_wrapping_quotes(value)
    if not path.lower().startswith("file://"):
        return path
    parsed = urlparse(path)
    decoded = unquote(parsed.path or "")
    if _WINDOWS_FILE_URL_PATH.match(decoded.replace("\\", "/")):
        return decoded[1:]
    if parsed.netloc and re.fullmatch(r"[A-Za-z]:", parsed.netloc):
        return f"{parsed.netloc}{decoded}"
    if os.name == "nt" and parsed.netloc and parsed.netloc.lower() not in {"", "localhost"}:
        return f"//{parsed.netloc}{decoded}"
    return decoded


def _clean_directory_path(value: str) -> str:
    path = _decode_file_url(value)
    path = os.path.expandvars(os.path.expanduser(path))
    return os.path.normpath(path) if path else path


def _manual_windows_to_wsl_path(value: str) -> str | None:
    path = _decode_file_url(value).replace("\\", "/")
    match = _WINDOWS_DRIVE_PATH.match(path)
    if not match:
        match = _WINDOWS_FILE_URL_PATH.match(path)
    if not match:
        return None
    drive, tail = match.groups()
    tail = tail.replace("\\", "/").lstrip("/")
    return os.path.normpath(f"/mnt/{drive.lower()}/{tail}")


def _windows_to_wsl_path(value: str) -> str | None:
    if os.name == "nt":
        return None
    raw = _decode_file_url(value)
    if not _WINDOWS_DRIVE_PATH.match(raw.replace("\\", "/")):
        return None
    if _is_wsl():
        try:
            result = subprocess.run(["wslpath", "-u", raw], check=True, capture_output=True, text=True, timeout=2)
            converted = result.stdout.strip()
            if converted:
                return os.path.normpath(converted)
        except (OSError, subprocess.SubprocessError):
            pass
    return _manual_windows_to_wsl_path(raw)


def _directory_candidates(path: str) -> list[str]:
    raw = _strip_wrapping_quotes(path)
    cleaned = _clean_directory_path(raw)
    converted = _windows_to_wsl_path(raw)
    candidates: list[str] = []
    if converted:
        candidates.append(converted)
    if cleaned and cleaned not in candidates:
        candidates.append(cleaned)
    return candidates


def normalize_source_spec(spec: dict[str, Any] | None) -> dict[str, str]:
    raw = spec if isinstance(spec, dict) else {}
    source_type = str(raw.get("type") or SOURCE_GITHUB).strip().lower()
    if source_type == SOURCE_GITHUB:
        return {"type": SOURCE_GITHUB, "repo": str(raw.get("repo") or SOURCE_REPO).strip(), "branch": str(raw.get("branch") or "main").strip()}
    if source_type == SOURCE_DIRECTORY:
        path = _strip_wrapping_quotes(str(raw.get("path") or ""))
        if not path:
            raise ProjectorError("SP_SOURCE_DIRECTORY_REQUIRED", "Local directory source requires a path")
        return {"type": SOURCE_DIRECTORY, "path": path}
    raise ProjectorError("SP_SOURCE_TYPE", f"Unsupported source type: {source_type!r}")


def _resolve_directory(path: str) -> Path:
    candidates = _directory_candidates(path)
    errors: list[Exception] = []
    for candidate in candidates:
        try:
            root = Path(candidate).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            errors.append(exc)
            continue
        if root.is_dir():
            return root
        errors.append(NotADirectoryError(candidate))
    message = f"Unable to resolve local directory: {path!r}"
    if candidates:
        message += f"; tried: {', '.join(repr(item) for item in candidates)}"
    raise ProjectorError("SP_SOURCE_DIRECTORY_INVALID", message) from (errors[-1] if errors else None)


def directory_roots() -> list[str]:
    if os.name == "nt":
        return [f"{letter}:\\" for letter in string.ascii_uppercase if os.path.isdir(f"{letter}:\\")]
    roots = [os.path.sep]
    if _is_wsl():
        mount_root = Path("/mnt")
        if mount_root.is_dir():
            for letter in string.ascii_lowercase:
                candidate = mount_root / letter
                if candidate.is_dir():
                    roots.append(str(candidate))
    return roots


def _nested_canonical_root(files: dict[str, bytes]) -> tuple[str, str] | None:
    """Locate exactly one explicit Contract Format bootstrap below the selected source.

    This is source mounting, not semantic inference: the bootstrap filename is the
    explicit canonical format marker. Ambiguous multiple canonical roots are not
    selected automatically.
    """
    matches: list[tuple[str, str]] = []
    suffixes = (
        (f"canonical/json/{CANONICAL_BOOTSTRAP}", "project_root"),
        (f"json/{CANONICAL_BOOTSTRAP}", "canonical_root"),
        (CANONICAL_BOOTSTRAP, "canonical_json_root"),
    )
    for path in sorted(files):
        normalized = path.replace("\\", "/")
        for suffix, kind in suffixes:
            if normalized == suffix or normalized.endswith("/" + suffix):
                prefix = normalized[:-len(suffix)].rstrip("/")
                matches.append((prefix, kind))
                break
    unique = sorted(set(matches))
    return unique[0] if len(unique) == 1 else None


def _canonical_mount(files: dict[str, bytes]) -> tuple[dict[str, bytes], str | None]:
    if f"canonical/json/{CANONICAL_BOOTSTRAP}" in files:
        return files, "project_root"
    if f"json/{CANONICAL_BOOTSTRAP}" in files:
        return {f"canonical/{path}": payload for path, payload in files.items()}, "canonical_root"
    if CANONICAL_BOOTSTRAP in files:
        return {f"canonical/json/{path}": payload for path, payload in files.items()}, "canonical_json_root"

    nested = _nested_canonical_root(files)
    if nested is None:
        return files, None

    prefix, kind = nested
    prefix_with_slash = f"{prefix}/" if prefix else ""
    scoped = {
        path[len(prefix_with_slash):]: payload
        for path, payload in files.items()
        if path == prefix or path.startswith(prefix_with_slash)
    }
    if kind == "project_root":
        return scoped, "nested_project_root"
    if kind == "canonical_root":
        return {f"canonical/{path}": payload for path, payload in scoped.items()}, "nested_canonical_root"
    return {f"canonical/json/{path}": payload for path, payload in scoped.items()}, "nested_canonical_json_root"


def _directory_format_hint(root: Path) -> str:
    if (root / "canonical" / "json" / CANONICAL_BOOTSTRAP).is_file():
        return "canonical_project_root"
    if (root / "json" / CANONICAL_BOOTSTRAP).is_file():
        return "canonical_root"
    if (root / CANONICAL_BOOTSTRAP).is_file():
        return "canonical_json_root"
    try:
        matches = list(root.glob(f"**/{CANONICAL_BOOTSTRAP}"))
        if len(matches) == 1:
            return "contains_canonical"
    except OSError:
        pass
    return "directory"


def browse_directories(path: str | None = None) -> dict[str, Any]:
    root = _resolve_directory(path) if path else Path.cwd().resolve()
    try:
        directories = [{"name": item.name, "path": str(item), "source_format": _directory_format_hint(item)} for item in sorted(root.iterdir(), key=lambda item: item.name.lower()) if item.is_dir() and not item.is_symlink() and item.name != ".git"]
    except (OSError, PermissionError) as exc:
        raise ProjectorError("SP_SOURCE_DIRECTORY_BROWSE", f"Unable to browse local directory: {str(root)!r}") from exc
    parent = root.parent if root.parent != root else None
    return {"path": str(root), "parent": str(parent) if parent is not None else None, "roots": directory_roots(), "source_format": _directory_format_hint(root), "directories": directories}


def load_directory_snapshot(path: str) -> SourceSnapshot:
    root = _resolve_directory(path)
    files: dict[str, bytes] = {}
    digest = hashlib.sha256()
    try:
        for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            dirs[:] = sorted(name for name in dirs if name != ".git" and not (current_path / name).is_symlink())
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
    mounted_files, _ = _canonical_mount(files)
    return SourceSnapshot(repo=f"directory:{root}", branch="local", revision=digest.hexdigest(), files=mounted_files)


def load_source(spec: dict[str, Any] | None) -> SourceSnapshot:
    normalized = normalize_source_spec(spec)
    if normalized["type"] == SOURCE_DIRECTORY:
        return load_directory_snapshot(normalized["path"])
    return load_snapshot(branch=normalized["branch"], repo=normalized["repo"])


def source_spec_from_query(query: dict[str, list[str]]) -> dict[str, str]:
    source_type = (query.get("source_type") or [SOURCE_GITHUB])[0]
    if source_type == SOURCE_DIRECTORY:
        return {"type": SOURCE_DIRECTORY, "path": (query.get("source_path") or [""])[0]}
    return {"type": SOURCE_GITHUB, "repo": (query.get("repo") or [SOURCE_REPO])[0], "branch": (query.get("branch") or ["main"])[0]}


def source_summary(snapshot: SourceSnapshot) -> dict[str, Any]:
    source_type = SOURCE_DIRECTORY if str(snapshot.repo).startswith("directory:") else SOURCE_GITHUB
    return {"type": source_type, "repository": snapshot.repo, "branch": snapshot.branch, "revision": snapshot.revision, "files": len(snapshot.files)}
