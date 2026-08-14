from __future__ import annotations

import hashlib
import json
import os
import re
import string
import subprocess
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.parse import unquote, urlparse

from source_adapter import load_snapshot
from structure_runtime import SUGGESTED_SOURCE_REPO, SourceSnapshot, StructureError

SOURCE_GITHUB = "github"
SOURCE_DIRECTORY = "directory"
CANONICAL_BOOTSTRAP = "00_Contract_Format.json"
_WINDOWS_DRIVE_PATH = re.compile(r"^([A-Za-z]):[\\/](.*)$")
_WINDOWS_FILE_URL_PATH = re.compile(r"^/([A-Za-z]):/(.*)$")
_SOURCE_LOCK = RLock()
_SOURCE_SNAPSHOT_CACHE: dict[str, SourceSnapshot] = {}


def _is_wsl() -> bool:
    if os.name == "nt": return False
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"): return True
    try: return "microsoft" in Path("/proc/version").read_text(encoding="utf-8", errors="ignore").lower()
    except OSError: return False


def _strip_wrapping_quotes(value: str) -> str:
    path = str(value or "").strip()
    if len(path) >= 2 and path[0] == path[-1] and path[0] in {"'", '"'}: return path[1:-1].strip()
    return path


def _decode_file_url(value: str) -> str:
    path = _strip_wrapping_quotes(value)
    if not path.lower().startswith("file://"): return path
    parsed = urlparse(path); decoded = unquote(parsed.path or "")
    if _WINDOWS_FILE_URL_PATH.match(decoded.replace("\\", "/")): return decoded[1:]
    if parsed.netloc and re.fullmatch(r"[A-Za-z]:", parsed.netloc): return f"{parsed.netloc}{decoded}"
    if os.name == "nt" and parsed.netloc and parsed.netloc.lower() not in {"", "localhost"}: return f"//{parsed.netloc}{decoded}"
    return decoded


def _clean_directory_path(value: str) -> str:
    path = _decode_file_url(value); path = os.path.expandvars(os.path.expanduser(path))
    return os.path.normpath(path) if path else path


def _manual_windows_to_wsl_path(value: str) -> str | None:
    path = _decode_file_url(value).replace("\\", "/"); match = _WINDOWS_DRIVE_PATH.match(path) or _WINDOWS_FILE_URL_PATH.match(path)
    if not match: return None
    drive, tail = match.groups(); return os.path.normpath(f"/mnt/{drive.lower()}/{tail.lstrip('/')}")


def _windows_to_wsl_path(value: str) -> str | None:
    if os.name == "nt": return None
    raw = _decode_file_url(value)
    if not _WINDOWS_DRIVE_PATH.match(raw.replace("\\", "/")): return None
    if _is_wsl():
        try:
            result = subprocess.run(["wslpath", "-u", raw], check=True, capture_output=True, text=True, timeout=2)
            if result.stdout.strip(): return os.path.normpath(result.stdout.strip())
        except (OSError, subprocess.SubprocessError): pass
    return _manual_windows_to_wsl_path(raw)


def _directory_candidates(path: str) -> list[str]:
    raw = _strip_wrapping_quotes(path); cleaned = _clean_directory_path(raw); converted = _windows_to_wsl_path(raw); out=[]
    if converted: out.append(converted)
    if cleaned and cleaned not in out: out.append(cleaned)
    return out


def normalize_source_spec(spec: dict[str, Any] | None) -> dict[str, str]:
    raw = spec if isinstance(spec, dict) else {}; source_type = str(raw.get("type") or SOURCE_GITHUB).strip().lower()
    if source_type == SOURCE_GITHUB: return {"type": SOURCE_GITHUB, "repo": str(raw.get("repo") or SUGGESTED_SOURCE_REPO).strip(), "branch": str(raw.get("branch") or "main").strip()}
    if source_type == SOURCE_DIRECTORY:
        path = _strip_wrapping_quotes(str(raw.get("path") or ""))
        if not path: raise StructureError("SP_SOURCE_DIRECTORY_REQUIRED", "Local directory source requires a path")
        return {"type": SOURCE_DIRECTORY, "path": path}
    raise StructureError("SP_SOURCE_TYPE", f"Unsupported source type: {source_type!r}")


def _source_cache_key(normalized: dict[str, str]) -> str:
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _resolve_directory(path: str) -> Path:
    errors=[]; candidates=_directory_candidates(path)
    for candidate in candidates:
        try: root=Path(candidate).resolve(strict=True)
        except (OSError, RuntimeError) as exc: errors.append(exc); continue
        if root.is_dir(): return root
        errors.append(NotADirectoryError(candidate))
    message=f"Unable to resolve local directory: {path!r}" + (f"; tried: {', '.join(repr(x) for x in candidates)}" if candidates else "")
    raise StructureError("SP_SOURCE_DIRECTORY_INVALID", message) from (errors[-1] if errors else None)


def directory_roots() -> list[str]:
    if os.name == "nt": return [f"{x}:\\" for x in string.ascii_uppercase if os.path.isdir(f"{x}:\\")]
    roots=[os.path.sep]
    if _is_wsl():
        for x in string.ascii_lowercase:
            p=Path("/mnt")/x
            if p.is_dir(): roots.append(str(p))
    return roots


def _direct_format_hint(root: Path) -> str:
    if (root / "canonical" / "json" / CANONICAL_BOOTSTRAP).is_file(): return "canonical_project_root"
    if (root / "json" / CANONICAL_BOOTSTRAP).is_file(): return "canonical_root"
    if (root / CANONICAL_BOOTSTRAP).is_file(): return "canonical_json_root"
    return "directory"


def _canonical_mount(files: dict[str, bytes]) -> tuple[dict[str, bytes], str | None]:
    direct=(f"canonical/json/{CANONICAL_BOOTSTRAP}", f"json/{CANONICAL_BOOTSTRAP}", CANONICAL_BOOTSTRAP)
    if direct[0] in files: return files, "project_root"
    if direct[1] in files: return {f"canonical/{p}":v for p,v in files.items()}, "canonical_root"
    if direct[2] in files: return {f"canonical/json/{p}":v for p,v in files.items()}, "canonical_json_root"
    roots=[]
    for path in files:
        p=path.replace("\\","/")
        if p.endswith("/canonical/json/"+CANONICAL_BOOTSTRAP): roots.append((p[:-len("canonical/json/"+CANONICAL_BOOTSTRAP)].rstrip("/"),"project"))
        elif p.endswith("/json/"+CANONICAL_BOOTSTRAP): roots.append((p[:-len("json/"+CANONICAL_BOOTSTRAP)].rstrip("/"),"canonical"))
        elif p.endswith("/"+CANONICAL_BOOTSTRAP): roots.append((p[:-len(CANONICAL_BOOTSTRAP)].rstrip("/"),"json"))
    roots=sorted(set(roots))
    if len(roots)!=1: return files,None
    prefix,kind=roots[0]; base=(prefix+"/") if prefix else ""
    scoped={p[len(base):]:v for p,v in files.items() if p.startswith(base)}
    if kind=="project": return scoped,"nested_project_root"
    if kind=="canonical": return {f"canonical/{p}":v for p,v in scoped.items()},"nested_canonical_root"
    return {f"canonical/json/{p}":v for p,v in scoped.items()},"nested_canonical_json_root"


def browse_directories(path: str | None = None) -> dict[str, Any]:
    root=_resolve_directory(path) if path else Path.cwd().resolve()
    try:
        directories=[]
        with os.scandir(root) as scan:
            for item in scan:
                try:
                    if item.name==".git" or item.is_symlink() or not item.is_dir(follow_symlinks=False): continue
                    p=Path(item.path); directories.append({"name":item.name,"path":str(p),"source_format":_direct_format_hint(p)})
                except OSError: continue
        directories.sort(key=lambda x:x["name"].lower())
    except (OSError,PermissionError) as exc:
        raise StructureError("SP_SOURCE_DIRECTORY_BROWSE",f"Unable to browse local directory: {str(root)!r}") from exc
    parent=root.parent if root.parent!=root else None
    return {"path":str(root),"parent":str(parent) if parent else None,"roots":directory_roots(),"source_format":_direct_format_hint(root),"directories":directories}


def load_directory_snapshot(path: str) -> SourceSnapshot:
    root=_resolve_directory(path); files={}; digest=hashlib.sha256()
    try:
        for current,dirs,names in os.walk(root,topdown=True,followlinks=False):
            current_path=Path(current); dirs[:]=sorted(n for n in dirs if n!=".git" and not (current_path/n).is_symlink())
            for name in sorted(names):
                absolute=current_path/name
                if absolute.is_symlink() or not absolute.is_file(): continue
                relative=absolute.relative_to(root).as_posix(); payload=absolute.read_bytes(); files[relative]=payload
                encoded=relative.encode("utf-8"); digest.update(len(encoded).to_bytes(8,"big")); digest.update(encoded); digest.update(len(payload).to_bytes(8,"big")); digest.update(payload)
    except (OSError,PermissionError) as exc:
        raise StructureError("SP_SOURCE_DIRECTORY_READ",f"Unable to read local directory source: {str(root)!r}") from exc
    mounted_files,_=_canonical_mount(files)
    return SourceSnapshot(repo=f"directory:{root}",branch="local",revision=digest.hexdigest(),files=mounted_files)


def load_source(spec: dict[str, Any] | None, *, refresh: bool = False) -> SourceSnapshot:
    normalized=normalize_source_spec(spec); key=_source_cache_key(normalized)
    with _SOURCE_LOCK:
        if not refresh and key in _SOURCE_SNAPSHOT_CACHE:
            return _SOURCE_SNAPSHOT_CACHE[key]
    snapshot=load_directory_snapshot(normalized["path"]) if normalized["type"]==SOURCE_DIRECTORY else load_snapshot(branch=normalized["branch"],repo=normalized["repo"])
    with _SOURCE_LOCK:
        _SOURCE_SNAPSHOT_CACHE[key]=snapshot
    return snapshot


def clear_source_snapshot_cache(spec: dict[str, Any] | None = None) -> None:
    with _SOURCE_LOCK:
        if spec is None:
            _SOURCE_SNAPSHOT_CACHE.clear()
        else:
            _SOURCE_SNAPSHOT_CACHE.pop(_source_cache_key(normalize_source_spec(spec)),None)


def source_spec_from_query(query: dict[str,list[str]]) -> dict[str,str]:
    source_type=(query.get("source_type") or [SOURCE_GITHUB])[0]
    if source_type==SOURCE_DIRECTORY: return {"type":SOURCE_DIRECTORY,"path":(query.get("source_path") or [""])[0]}
    return {"type":SOURCE_GITHUB,"repo":(query.get("repo") or [SUGGESTED_SOURCE_REPO])[0],"branch":(query.get("branch") or ["main"])[0]}


def source_summary(snapshot: SourceSnapshot) -> dict[str,Any]:
    source_type=SOURCE_DIRECTORY if str(snapshot.repo).startswith("directory:") else SOURCE_GITHUB
    return {"type":source_type,"repository":snapshot.repo,"branch":snapshot.branch,"revision":snapshot.revision,"files":len(snapshot.files)}
