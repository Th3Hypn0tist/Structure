from __future__ import annotations

from typing import Any

from raw_json_mapper import build_raw_json_graph
from structure_tree import add_entry, add_link, new_tree, validate_tree


def read(snapshot: Any, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read one JSON source into neutral StructureTree using JSON syntax only."""
    options = options or {}
    result = build_raw_json_graph(snapshot, options.get("path"))
    tree = new_tree(input_module="raw_json", source=result.get("source", {}))

    graph = result.get("graph", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    parent_by_child: dict[str, str] = {}
    relation_by_child: dict[str, dict[str, Any]] = {}
    for edge in edges:
        if edge.get("dimension") == "containment" and edge.get("source") and edge.get("target"):
            parent_by_child[str(edge["target"])] = str(edge["source"])
            relation_by_child[str(edge["target"])] = edge.get("raw") or {}

    for node in nodes:
        node_id = str(node.get("id"))
        if not node_id:
            continue
        add_entry(
            tree,
            entry_id=node_id,
            name=str(node.get("name") or node_id),
            kind="raw_json",
            parent_id=parent_by_child.get(node_id),
            entry_type=node.get("type"),
            status=None,
            metadata={
                "pointer": node.get("pointer"),
                "value": node.get("value"),
                "json": node.get("raw"),
                "parent_relation": relation_by_child.get(node_id),
            },
            provenance={
                "path": node.get("source"),
                "pointer": node.get("pointer"),
                "repository": snapshot.repo,
                "branch": snapshot.branch,
                "revision": snapshot.revision,
            },
        )

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        add_link(
            tree,
            link_id=edge.get("id"),
            source_id=str(source),
            target_id=str(target),
            dimension=str(edge.get("dimension") or "containment"),
            link_type=edge.get("type") or "contains",
            metadata={"raw": edge.get("raw")},
            provenance={
                "path": result.get("source", {}).get("path"),
                "repository": snapshot.repo,
                "branch": snapshot.branch,
                "revision": snapshot.revision,
            },
        )

    tree["errors"] = list(result.get("errors", []))
    tree["warnings"] = list(result.get("warnings", []))
    tree["validation_errors"] = validate_tree(tree)
    tree["valid"] = bool(result.get("valid")) and not tree["validation_errors"]
    tree["projectable"] = bool(result.get("valid"))
    return tree
