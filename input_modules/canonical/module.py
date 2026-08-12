from __future__ import annotations

from typing import Any

from canonical_graph import build_graph
from structure_tree import add_entry, add_link, new_tree, validate_tree


def read(snapshot: Any, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read Canonical source into neutral StructureTree.

    This module preserves only explicit structure already proven by the
    canonical parser. It performs no layout, primitive selection, styling or
    renderer-specific interpretation.
    """
    result = build_graph(snapshot)
    tree = new_tree(input_module="canonical", source=result.get("source", {}))

    graph = result.get("graph", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    parent_by_child: dict[str, str] = {}
    for edge in edges:
        if edge.get("dimension") == "containment" and edge.get("source") and edge.get("target"):
            parent_by_child.setdefault(str(edge["target"]), str(edge["source"]))

    for node in nodes:
        node_id = str(node.get("id"))
        if not node_id:
            continue
        add_entry(
            tree,
            entry_id=node_id,
            name=str(node.get("name") or node_id),
            kind=str(node.get("kind") or "canonical"),
            parent_id=parent_by_child.get(node_id),
            entry_type=node.get("type"),
            status=node.get("status"),
            metadata={
                "source_role": node.get("source_role"),
                "semantics": node.get("semantics", {}),
            },
            provenance={
                "path": node.get("source"),
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
            dimension=str(edge.get("dimension") or "relation"),
            link_type=edge.get("type"),
            metadata={"raw": edge.get("raw")},
            provenance={
                "repository": snapshot.repo,
                "branch": snapshot.branch,
                "revision": snapshot.revision,
            },
        )

    tree["errors"] = list(result.get("errors", []))
    tree["warnings"] = list(result.get("warnings", []))
    tree["validation_errors"] = validate_tree(tree)
    tree["valid"] = bool(result.get("valid")) and not tree["validation_errors"]
    tree["projectable"] = bool(result.get("projectable"))
    tree["source_result"] = {
        "projection_status": result.get("projection_status"),
        "format": result.get("format"),
        "master": result.get("master"),
        "diagnostics": result.get("diagnostics"),
    }
    return tree
