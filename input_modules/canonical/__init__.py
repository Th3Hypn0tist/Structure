from cw14_model import is_v14
from structure_tree import validate_tree

from input_modules.directory import read as read_directory
from .cw14 import enrich_v14
from .cw_flow import enrich
from .module import read as _read
from .topic_enrichment import enrich_topics

BOOTSTRAP = "00_Contract_Format.json"


def _canonical_candidates(snapshot):
    """Return explicit canonical roots identified by the bootstrap contract.

    This is format discovery, not semantic inference. The bootstrap itself is the
    explicit authority that identifies a canonical source subtree.
    """
    candidates = []
    for path in sorted(snapshot.files):
        normalized = path.replace("\\", "/")
        if normalized == f"canonical/json/{BOOTSTRAP}":
            candidates.append(("", "project"))
        elif normalized == f"json/{BOOTSTRAP}":
            candidates.append(("", "canonical"))
        elif normalized == BOOTSTRAP:
            candidates.append(("", "json"))
        elif normalized.endswith(f"/canonical/json/{BOOTSTRAP}"):
            prefix = normalized[: -len(f"canonical/json/{BOOTSTRAP}")].rstrip("/")
            candidates.append((prefix, "project"))
        elif normalized.endswith(f"/json/{BOOTSTRAP}"):
            prefix = normalized[: -len(f"json/{BOOTSTRAP}")].rstrip("/")
            candidates.append((prefix, "canonical"))
        elif normalized.endswith(f"/{BOOTSTRAP}"):
            prefix = normalized[: -len(BOOTSTRAP)].rstrip("/")
            candidates.append((prefix, "json"))
    return sorted(set(candidates))


def _canonicalized_snapshot(snapshot):
    candidates = _canonical_candidates(snapshot)
    if not candidates:
        return None
    if len(candidates) > 1:
        rendered = ", ".join(f"{prefix or '.'}:{kind}" for prefix, kind in candidates)
        raise ValueError(f"Multiple canonical bootstrap roots found in selected source: {rendered}")

    prefix, kind = candidates[0]
    base = f"{prefix}/" if prefix else ""
    scoped = {
        path[len(base):]: payload
        for path, payload in snapshot.files.items()
        if not base or path.startswith(base)
    }

    if kind == "project":
        files = scoped
    elif kind == "canonical":
        files = {f"canonical/{path}": payload for path, payload in scoped.items()}
    else:
        files = {f"canonical/json/{path}": payload for path, payload in scoped.items()}

    return type(snapshot)(
        repo=snapshot.repo,
        branch=snapshot.branch,
        revision=snapshot.revision,
        files=files,
    )


def read(snapshot, options=None):
    canonical_snapshot = _canonicalized_snapshot(snapshot)
    if canonical_snapshot is None:
        tree = read_directory(snapshot, options)
        tree.setdefault("source_result", {})["canonical_reader"] = {
            "enabled": False,
            "mode": "directory",
            "reason": "no explicit canonical bootstrap found",
        }
        return tree

    snapshot = canonical_snapshot
    tree = _read(snapshot, options)

    if is_v14(snapshot):
        tree = enrich_v14(tree, snapshot)
    else:
        tree = enrich(tree, snapshot)

    tree = enrich_topics(tree, snapshot)
    tree.setdefault("source_result", {})["canonical_reader"] = {
        "enabled": True,
        "mode": "canonical",
        "bootstrap": f"canonical/json/{BOOTSTRAP}",
    }
    tree["validation_errors"] = validate_tree(tree)
    tree["valid"] = bool(tree.get("valid")) and not tree.get("errors") and not tree["validation_errors"]
    tree["projectable"] = bool(tree.get("projectable")) and not tree.get("errors") and not tree["validation_errors"]
    return tree


__all__ = ["read"]
