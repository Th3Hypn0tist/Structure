from __future__ import annotations

from copy import deepcopy
from typing import Any

FORMAT = "STRUCTUREPROJECTOR_STRUCTURE_TREE"
VERSION = "1.0"


def new_tree(*, input_module: str, source: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": FORMAT,
        "version": VERSION,
        "input_module": input_module,
        "source": deepcopy(source),
        "roots": [],
        "entries": [],
        "links": [],
        "errors": [],
        "warnings": [],
    }


def add_entry(
    tree: dict[str, Any],
    *,
    entry_id: str,
    name: str,
    kind: str,
    parent_id: str | None,
    entry_type: str | None = None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry = {
        "id": entry_id,
        "name": name,
        "kind": kind,
        "type": entry_type,
        "parent_id": parent_id,
        "status": status,
        "metadata": deepcopy(metadata or {}),
        "provenance": deepcopy(provenance or {}),
    }
    tree["entries"].append(entry)
    if parent_id is None:
        tree["roots"].append(entry_id)
    return entry


def add_link(
    tree: dict[str, Any],
    *,
    link_id: str | None,
    source_id: str,
    target_id: str,
    dimension: str,
    link_type: str | None = None,
    metadata: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    link = {
        "id": link_id,
        "source_id": source_id,
        "target_id": target_id,
        "dimension": dimension,
        "type": link_type or dimension,
        "metadata": deepcopy(metadata or {}),
        "provenance": deepcopy(provenance or {}),
    }
    tree["links"].append(link)
    return link


def validate_tree(tree: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if tree.get("format") != FORMAT:
        errors.append({"id": "SP_TREE_FORMAT", "message": f"Expected {FORMAT}"})
    if tree.get("version") != VERSION:
        errors.append({"id": "SP_TREE_VERSION", "message": f"Expected StructureTree version {VERSION}"})

    entries = tree.get("entries")
    links = tree.get("links")
    if not isinstance(entries, list):
        return errors + [{"id": "SP_TREE_ENTRIES", "message": "entries must be an array"}]
    if not isinstance(links, list):
        return errors + [{"id": "SP_TREE_LINKS", "message": "links must be an array"}]

    ids: set[str] = set()
    for entry in entries:
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            errors.append({"id": "SP_TREE_ENTRY_ID", "message": "Every entry requires a non-empty id"})
            continue
        if entry_id in ids:
            errors.append({"id": "SP_TREE_DUPLICATE_ID", "message": f"Duplicate StructureTree entry: {entry_id}"})
        ids.add(entry_id)

    for entry in entries:
        parent_id = entry.get("parent_id")
        if parent_id is not None and parent_id not in ids:
            errors.append({"id": "SP_TREE_PARENT", "message": f"Unresolved parent_id: {parent_id}", "entry": entry.get("id")})

    for link in links:
        source_id = link.get("source_id")
        target_id = link.get("target_id")
        if source_id not in ids:
            errors.append({"id": "SP_TREE_LINK_SOURCE", "message": f"Unresolved link source: {source_id}"})
        if target_id not in ids:
            errors.append({"id": "SP_TREE_LINK_TARGET", "message": f"Unresolved link target: {target_id}"})
    return errors


def tree_to_graph(tree: dict[str, Any]) -> dict[str, Any]:
    """Compatibility adapter for current projection engines.

    This performs no layout and introduces no semantics. It only translates the
    neutral StructureTree field names to the existing normalized graph shape.
    """
    nodes = []
    for entry in tree.get("entries", []):
        nodes.append({
            "id": entry.get("id"),
            "name": entry.get("name"),
            "type": entry.get("type"),
            "status": entry.get("status"),
            "source_role": entry.get("metadata", {}).get("source_role"),
            "source": entry.get("provenance", {}).get("path"),
            "kind": entry.get("kind"),
            "raw": deepcopy(entry),
        })

    edges = []
    for link in tree.get("links", []):
        edges.append({
            "id": link.get("id"),
            "dimension": link.get("dimension"),
            "source": link.get("source_id"),
            "target": link.get("target_id"),
            "type": link.get("type"),
            "raw": deepcopy(link),
        })

    # Directory parenthood is structural input information. Expose it as an
    # explicit containment edge only when no identical link already exists.
    existing = {(e["source"], e["target"], e["dimension"]) for e in edges}
    for entry in tree.get("entries", []):
        parent_id = entry.get("parent_id")
        if parent_id is None:
            continue
        key = (parent_id, entry.get("id"), "tree")
        if key in existing:
            continue
        edges.append({
            "id": f"tree:{parent_id}->{entry.get('id')}",
            "dimension": "tree",
            "source": parent_id,
            "target": entry.get("id"),
            "type": "contains",
            "raw": {"source": "StructureTree.parent_id"},
        })
    return {"nodes": nodes, "edges": edges}
