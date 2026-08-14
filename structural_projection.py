from __future__ import annotations

from copy import deepcopy
from collections import deque
from typing import Any


STRUCTURAL_DIMENSIONS = {
    "dependency": "dependencies",
    "relation": "relations",
    "authority": "authority",
    "ownership": "ownership",
    "containment": "containment",
}


def _node_index(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(node.get("id")): node
        for node in graph.get("nodes", [])
        if isinstance(node, dict) and node.get("id") is not None
    }


def _topic_record(tree: dict[str, Any], scope_ref: str) -> dict[str, Any] | None:
    index = tree.get("topic_index") if isinstance(tree.get("topic_index"), dict) else {}
    for item in index.get("headings", []):
        if isinstance(item, dict) and str(item.get("id")) == scope_ref:
            return item
    topics = index.get("topics") if isinstance(index.get("topics"), dict) else {}
    item = topics.get(scope_ref)
    return item if isinstance(item, dict) else None


def _base_ids(tree: dict[str, Any], graph: dict[str, Any], scope_type: str, scope_ref: str) -> tuple[set[str], str]:
    nodes = _node_index(graph)
    if scope_type == "identity":
        if scope_ref not in nodes:
            raise KeyError(f"Unknown projection identity: {scope_ref}")
        return {scope_ref}, str(nodes[scope_ref].get("name") or scope_ref)
    if scope_type == "topic":
        record = _topic_record(tree, scope_ref)
        if record is None:
            raise KeyError(f"Unknown resolved Topic scope: {scope_ref}")
        refs = {str(ref) for ref in record.get("projection_base_ids", []) if str(ref) in nodes}
        return refs, str(record.get("label") or scope_ref)
    raise ValueError(f"Unsupported structural projection scope type: {scope_type}")


def structural_base_graph(
    tree: dict[str, Any],
    graph: dict[str, Any],
    *,
    projection_base: str,
    scope_type: str,
    scope_ref: str,
    max_depth: int = 0,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    dimension = STRUCTURAL_DIMENSIONS.get(projection_base)
    if dimension is None:
        raise ValueError(f"Projection base is not structural: {projection_base}")

    indexes = tree.get("indexes") if isinstance(tree.get("indexes"), dict) else {}
    link_index = indexes.get("links") if isinstance(indexes.get("links"), dict) else {}
    links_by_id = link_index.get("by_id") if isinstance(link_index.get("by_id"), dict) else {}
    by_dimension = link_index.get("by_dimension") if isinstance(link_index.get("by_dimension"), dict) else {}
    adjacency_by_dimension = link_index.get("adjacency_by_dimension") if isinstance(link_index.get("adjacency_by_dimension"), dict) else {}
    adjacency = adjacency_by_dimension.get(dimension) if isinstance(adjacency_by_dimension.get(dimension), dict) else {}
    selected_link_ids = [str(ref) for ref in by_dimension.get(dimension, [])]

    nodes_by_id = _node_index(graph)
    base_ids, root_name = _base_ids(tree, graph, scope_type, scope_ref)
    max_depth = max(0, min(32, int(max_depth)))

    depth_by_ref: dict[str, int] = {ref: 0 for ref in sorted(base_ids)}
    parent_by_ref: dict[str, str | None] = {ref: None for ref in sorted(base_ids)}
    queue = deque(sorted(base_ids))
    while queue:
        current = queue.popleft()
        current_depth = depth_by_ref[current]
        if current_depth >= max_depth:
            continue
        for neighbor in adjacency.get(current, []):
            neighbor = str(neighbor)
            if neighbor not in nodes_by_id or neighbor in depth_by_ref:
                continue
            depth_by_ref[neighbor] = current_depth + 1
            parent_by_ref[neighbor] = current
            queue.append(neighbor)

    included = set(depth_by_ref)
    nodes: list[dict[str, Any]] = []
    for node_id in sorted(included):
        raw = nodes_by_id.get(node_id)
        if raw is None:
            continue
        node = deepcopy(raw)
        depth = depth_by_ref[node_id]
        node["hierarchy_depth"] = depth
        node["projection_depth"] = depth
        node["projection_generation"] = depth + 1
        node["projection_parent_id"] = parent_by_ref.get(node_id)
        node["projection_dimension_semantic"] = dimension
        nodes.append(node)

    edges: list[dict[str, Any]] = []
    for link_id in selected_link_ids:
        raw = links_by_id.get(link_id)
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("source_id") or "")
        target = str(raw.get("target_id") or "")
        if source not in included or target not in included:
            continue
        edges.append({
            "id": link_id,
            "dimension": dimension,
            "source": source,
            "target": target,
            "type": raw.get("type") or dimension,
            "inference": False,
        })

    projected = {
        "nodes": nodes,
        "edges": edges,
        "projection_root": scope_ref,
        "projection_root_name": root_name,
        "projection_base_ids": sorted(base_ids),
        "projection_relation_depth": max_depth,
        "projection_external_references": [],
        "projection_semantic_kind": projection_base,
    }
    metadata = {
        "projection_base": projection_base,
        "scope_type": scope_type,
        "scope_ref": scope_ref,
        "edge_dimension": dimension,
        "relation_depth": max_depth,
        "base_node_count": len(base_ids),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "structure_tree_index_source": f"indexes.links.adjacency_by_dimension.{dimension}",
        "projection_reanalysis_required": False,
        "traversal": "bidirectional cached adjacency",
        "edge_direction_preserved": True,
        "other_dimensions_extend_surface": False,
        "inference": False,
    }
    return projected, metadata, depth_by_ref


__all__ = ["STRUCTURAL_DIMENSIONS", "structural_base_graph"]
