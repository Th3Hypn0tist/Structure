from cw14_model import is_v14
from structure_tree import validate_tree

from input_modules.directory import read as read_directory
from .cw14 import enrich_v14
from .cw_flow import enrich
from .module import read as _read
from .topic_enrichment import enrich_topics

FORMAT_ROOT_FILENAME = "AIGMos_Canonical_Contract_Format_v1.4.0.json"
LEGACY_BOOTSTRAP = "00_Contract_Format.json"


def _project_candidates(snapshot):
    """Discover projects only from the explicit Contract Format 1.4 authority."""
    candidates = []
    for path in sorted(snapshot.files):
        normalized = path.replace("\\", "/")
        if normalized == FORMAT_ROOT_FILENAME:
            candidates.append("")
        elif normalized.endswith(f"/{FORMAT_ROOT_FILENAME}"):
            candidates.append(normalized[: -len(FORMAT_ROOT_FILENAME)].rstrip("/"))
    return sorted(set(candidates))


def _canonicalized_snapshot(snapshot):
    candidates = _project_candidates(snapshot)
    if not candidates:
        return None
    if len(candidates) > 1:
        rendered = ", ".join(prefix or "." for prefix in candidates)
        raise ValueError(f"Multiple Contract Format 1.4 project roots found in selected source: {rendered}")

    prefix = candidates[0]
    base = f"{prefix}/" if prefix else ""
    scoped = {
        path[len(base):]: payload
        for path, payload in snapshot.files.items()
        if not base or path.startswith(base)
    }
    format_raw = scoped.get(FORMAT_ROOT_FILENAME)
    if format_raw is None:
        return None

    canonical_files = {
        path: payload
        for path, payload in scoped.items()
        if path.startswith("canonical/json/") and path.endswith(".json")
    }
    if not canonical_files:
        raise ValueError("Contract Format 1.4 bootstrap found, but canonical/json contains no canonical JSON contracts")

    files = dict(canonical_files)
    files[f"canonical/json/{LEGACY_BOOTSTRAP}"] = format_raw

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
            "reason": f"no project-root {FORMAT_ROOT_FILENAME} bootstrap authority found",
            "legacy_bootstrap_is_authority": False,
        }
        return tree

    snapshot = canonical_snapshot
    tree = _read(snapshot, options)

    if is_v14(snapshot):
        tree = enrich_v14(tree, snapshot)
        topic_reader = "cw14_native_resolved"
    else:
        tree = enrich(tree, snapshot)
        tree = enrich_topics(tree, snapshot)
        topic_reader = "generic_explicit"

    tree.setdefault("source_result", {})["canonical_reader"] = {
        "enabled": True,
        "mode": "canonical",
        "contract_format": "1.4" if is_v14(snapshot) else "pre-1.4",
        "bootstrap_authority": FORMAT_ROOT_FILENAME,
        "canonical_contract_root": "canonical/json/",
        "legacy_bootstrap_is_authority": False,
        "topic_reader": topic_reader,
        "discovery_inference": False,
    }

    # Validation findings describe the source; they do not make the source
    # unprojectable. Structure must be able to project incomplete, ambiguous and
    # internally inconsistent masters precisely so those gaps can be inspected.
    # Only failure to materialize a usable StructureTree is projection-blocking.
    base_projectable = bool(tree.get("projectable"))
    tree["validation_errors"] = validate_tree(tree)
    tree["valid"] = bool(tree.get("valid")) and not tree.get("errors") and not tree["validation_errors"]
    tree["projectable"] = base_projectable
    tree["degraded"] = bool(tree.get("errors") or tree["validation_errors"])
    tree["validation_finding_count"] = len(tree.get("errors", [])) + len(tree["validation_errors"])
    tree["source_result"]["canonical_reader"]["projection_policy"] = "validation_findings_do_not_block_projection"
    return tree


__all__ = ["read"]
