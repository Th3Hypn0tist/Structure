from __future__ import annotations

import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

from structureprojector import ProjectorError, SOURCE_REPO, SourceSnapshot

USER_AGENT = "StructureProjector/0.11"
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")

# Branch names are mutable; commit snapshots are not.
_branch_cache: dict[tuple[str, str], str] = {}
_snapshot_cache: dict[tuple[str, str], SourceSnapshot] = {}
_branches_cache: dict[str, tuple[float, list[dict[str, str]]]] = {}
BRANCH_LIST_TTL_SECONDS = 300


def _request_json(url: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def _atom_branch_sha(branch: str, repo: str) -> str:
    """Resolve a public GitHub branch without consuming REST API quota.

    The commits Atom feed exposes immutable commit URLs. We read only the first
    entry and accept it only if it contains an exact 40-hex commit SHA.
    """
    owner, name = repo.split("/", 1)
    quoted = urllib.parse.quote(branch, safe="/")
    url = f"https://github.com/{owner}/{name}/commits/{quoted}.atom"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/atom+xml"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise ProjectorError(
            "SP_SOURCE_BRANCH_RESOLVE",
            f"Unable to resolve branch {branch!r}: HTTP {exc.code}: {exc.reason}",
        ) from exc
    except urllib.error.URLError as exc:
        raise ProjectorError(
            "SP_SOURCE_UNAVAILABLE",
            f"GitHub source unavailable while resolving {branch!r}: {exc.reason}",
        ) from exc

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ProjectorError(
            "SP_SOURCE_BRANCH_RESOLVE",
            f"Invalid GitHub branch feed for {branch!r}",
        ) from exc

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", ns)
    if entry is None:
        raise ProjectorError(
            "SP_SOURCE_BRANCH_RESOLVE",
            f"No commits found for branch {branch!r}",
        )

    candidates: list[str] = []
    ident = entry.findtext("atom:id", default="", namespaces=ns)
    candidates.extend(re.findall(r"[0-9a-fA-F]{40}", ident))
    for link in entry.findall("atom:link", ns):
        href = link.attrib.get("href", "")
        candidates.extend(re.findall(r"[0-9a-fA-F]{40}", href))

    for candidate in candidates:
        if _SHA_RE.fullmatch(candidate):
            return candidate.lower()

    raise ProjectorError(
        "SP_SOURCE_BRANCH_RESOLVE",
        f"Branch feed did not expose an exact commit SHA for {branch!r}",
    )


def resolve_branch(branch: str, repo: str = SOURCE_REPO, *, refresh: bool = False) -> str:
    key = (repo, branch)
    if not refresh and key in _branch_cache:
        return _branch_cache[key]

    owner, name = repo.split("/", 1)
    quoted = urllib.parse.quote(branch, safe="")
    url = f"https://api.github.com/repos/{owner}/{name}/branches/{quoted}"
    try:
        data = _request_json(url)
        revision = str(data["commit"]["sha"]).lower()
        if not _SHA_RE.fullmatch(revision):
            raise ValueError("invalid commit SHA")
    except (urllib.error.HTTPError, urllib.error.URLError, KeyError, ValueError, TypeError):
        # Public GitHub REST is intentionally not a runtime dependency for
        # correctness. Rate-limit/network failures fall back to the public Atom
        # commit feed, which still resolves the branch to an immutable SHA.
        revision = _atom_branch_sha(branch, repo)

    _branch_cache[key] = revision
    return revision


def list_branches(repo: str = SOURCE_REPO, *, refresh: bool = False) -> list[dict[str, str]]:
    cached = _branches_cache.get(repo)
    if not refresh and cached and (time.monotonic() - cached[0]) < BRANCH_LIST_TTL_SECONDS:
        return [dict(item) for item in cached[1]]

    owner, name = repo.split("/", 1)
    out: list[dict[str, str]] = []
    try:
        page = 1
        while True:
            url = f"https://api.github.com/repos/{owner}/{name}/branches?per_page=100&page={page}"
            chunk = _request_json(url)
            if not chunk:
                break
            for item in chunk:
                branch = str(item["name"])
                sha = str(item["commit"]["sha"]).lower()
                if not _SHA_RE.fullmatch(sha):
                    continue
                out.append({"name": branch, "sha": sha})
                _branch_cache[(repo, branch)] = sha
            if len(chunk) < 100:
                break
            page += 1
    except (urllib.error.HTTPError, urllib.error.URLError, KeyError, TypeError):
        # Fail usable for the canonical default instead of taking the whole UI
        # down when unauthenticated GitHub REST quota is exhausted.
        main_sha = resolve_branch("main", repo, refresh=refresh)
        out = [{"name": "main", "sha": main_sha}]

    if not out:
        main_sha = resolve_branch("main", repo, refresh=refresh)
        out = [{"name": "main", "sha": main_sha}]

    _branches_cache[repo] = (time.monotonic(), [dict(item) for item in out])
    return out


def load_snapshot(
    branch: str,
    repo: str = SOURCE_REPO,
    *,
    revision: str | None = None,
    refresh: bool = False,
) -> SourceSnapshot:
    resolved = (revision or resolve_branch(branch, repo, refresh=refresh)).lower()
    if not _SHA_RE.fullmatch(resolved):
        raise ProjectorError(
            "SP_SOURCE_REVISION_INVALID",
            f"Source revision must be an exact 40-hex commit SHA: {resolved!r}",
        )

    cache_key = (repo, resolved)
    if cache_key in _snapshot_cache:
        return _snapshot_cache[cache_key]

    owner, name = repo.split("/", 1)
    url = f"https://codeload.github.com/{owner}/{name}/zip/{resolved}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise ProjectorError(
            "SP_SOURCE_ARCHIVE_HTTP",
            f"GitHub archive returned HTTP {exc.code}: {exc.reason}",
        ) from exc
    except urllib.error.URLError as exc:
        raise ProjectorError(
            "SP_SOURCE_ARCHIVE_UNAVAILABLE",
            f"GitHub archive unavailable: {exc.reason}",
        ) from exc

    files: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            prefix = names[0].split("/", 1)[0] + "/" if names else ""
            for name_in_zip in names:
                rel = (
                    name_in_zip[len(prefix):]
                    if name_in_zip.startswith(prefix)
                    else name_in_zip
                )
                if rel and not rel.startswith(".git/"):
                    files[rel] = archive.read(name_in_zip)
    except zipfile.BadZipFile as exc:
        raise ProjectorError(
            "SP_SOURCE_ARCHIVE_INVALID",
            "GitHub source archive is not a valid ZIP file",
        ) from exc

    snapshot = SourceSnapshot(
        repo=repo,
        branch=branch,
        revision=resolved,
        files=files,
    )
    _snapshot_cache[cache_key] = snapshot
    _branch_cache[(repo, branch)] = resolved
    return snapshot
