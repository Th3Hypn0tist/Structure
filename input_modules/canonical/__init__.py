from cw14_model import is_v14
from structure_tree import validate_tree

from input_modules.directory import read as read_directory
from .cw14 import enrich_v14
from .cw_flow import enrich
from .module import read as _read


def _has_canonical_bootstrap(snapshot) -> bool:
    files = set(snapshot.files)
    return (
        "canonical/json/00_Contract_Format.json" in files
        or "json/00_Contract_Format.json" in files
        or "00_Contract_Format.json" in files
    )


def _canonicalized_snapshot(snapshot):
    files = snapshot.files
    if "canonical/json/00_Contract_Format.json" in files:
        return snapshot

    if "json/00_Contract_Format.json" in files:
        prefix = "canonical/"
    elif "00_Contract_Format.json" in files:
        prefix = "canonical/json/"
    else:
        return snapshot

    return type(snapshot)(
        repo=snapshot.repo,
        branch=snapshot.branch,
        revision=snapshot.revision,
        files={f"{prefix}{path}": payload for path, payload in files.items()},
    )


def read(snapshot, options=None):
    if not _has_canonical_bootstrap(snapshot):
        return read_directory(snapshot, options)

    snapshot = _canonicalized_snapshot(snapshot)
    tree = _read(snapshot, options)
    if is_v14(snapshot):
        tree = enrich_v14(tree, snapshot)
        tree["validation_errors"] = validate_tree(tree)
        tree["valid"] = bool(tree.get("valid")) and not tree["validation_errors"]
        tree["projectable"] = bool(tree.get("projectable")) and not tree.get("errors") and not tree["validation_errors"]
        return tree
    return enrich(tree, snapshot)


__all__ = ["read"]
