from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any

from canonical_projections import PROJECTIONS as CORE_PROJECTIONS
from canonical_projections_extra3d import PROJECTIONS as EXTRA_PROJECTIONS
from structure_reveal_projections import PROJECTIONS as STRUCTURE_REVEAL_PROJECTIONS

MAX_RELATION_DEPTH = 32
PRIMARY_ROOT_IDS = ("IAM", "AccessCore", "DWH")

STYLE_LABELS = {
    "atlas_2d": "Atlas 2D",
    "relation_web_2d": "Map 2D",
    "adjacency_matrix_2d": "Matrix 2D",
    "lifecycle_lanes_2d": "Lifecycle Lanes 2D",
    "dependency_flow_2d": "Dependency Flow 2D",
    "atlas_3d": "Atlas 3D",
    "relation_web_3d": "Map 3D",
    "adjacency_matrix_3d": "Matrix 3D",
    "lifecycle_lanes_3d": "Lifecycle Lanes 3D",
    "dependency_flow_3d": "Dependency Flow 3D",
    "semantic_galaxy_3d": "Galaxy",
    "role_layers_3d": "Role Layers",
    "dependency_tower_3d": "Dependency Tower",
    "authority_space_3d": "Authority Space",
    "relation_orbits_3d": "Relation Orbits",
    "hierarchy_tree_2d": "Hierarchy Tree 2D",
    "relation_generations_2d": "Relation Generations 2D",
    "component_islands_2d": "Component Islands 2D",
    "relation_shells_3d": "Relation Shells 3D",
    "structure_spine_3d": "Structure Spine 3D",
}


def style_catalog() -> list[dict[str, Any]]:
    merged = {**CORE_PROJECTIONS, **EXTRA_PROJECTIONS, **STRUCTURE_REVEAL_PROJECTIONS}
    return sorted([
        {
            "id": style_id,
            "label": STYLE_LABELS.get(style_id, meta.get("title") or style_id),
            "dimension": meta.get("dimension"),
            "kind": meta.get("kind"),
        }
        for style_id, meta in merged.items()
    ], key=lambda item: (str(item.get("dimension")), str(item.get("kind")), str(item.get("label"))))


def _entries(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("id")): entry
        for entry in tree.get("entries", [])
        if entry.get("id") is not None
    }


def _children(entries: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for entry_id, entry in entries.items():
        parent_id = entry.get("parent_id")
        if parent_id is not None and str(parent_id) in entries:
            out.setdefault(str(parent_id), []).append(entry_id)
    for values in out.values():
        values.sort()
    return out


def _containment_subtree(root_id: str, entries: dict[str, dict[str, Any]]) -> set[str]:
    if root_id not in entries:
        return set()
    children = _children(entries)
    seen: set[str] = set()
    queue = deque([root_id])
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(children.get(current, []))
    return seen


def topic_catalog(tree: dict[str, Any]) -> list[dict[str, Any]]:
    entries = _entries(tree)
    ordered: list[str] = [root for root in PRIMARY_ROOT_IDS if root in entries]
    definitions = [
        entry_id for entry_id, entry in entries.items()
        if str((entry.get("metadata") or {}).get("source_role") or "") == "definition"
        and entry_id not in PRIMARY_ROOT_IDS
    ]
    definitions.sort(key=lambda entry_id: str(entries[entry_id].get("name") or entry_id).lower())
    ordered.extend(definitions)
    return [
        {
            "id": entry_id,
            "label": str(entries[entry_id].get("name") or entry_id),
            "entry_count": len(_containment_subtree(entry_id, entries)),
            "primary": entry_id in PRIMARY_ROOT_IDS,
        }
        for entry_id in ordered
    ]


def _projection_hierarchy_depths(tree: dict[str, Any], included: set[str]) -> dict[str, int | None]:
    parents = {
        str(entry.get("id")): (str(entry.get("parent_id")) if entry.get("parent_id") is not None else None)
        for entry in tree.get("entries", [])
        if entry.get("id") is not None and str(entry.get("id")) in included
    }
    memo: dict[str, int | None] = {}

    def depth(entry_id: str, stack: set[str]) -> int | None:
        if entry_id in memo:
            return memo[entry_id]
        if entry_id in stack:
            memo[entry_id] = None
            return None
        parent_id = parents.get(entry_id)
        if parent_id is None or parent_id not in included:
            memo[entry_id] = 0
            return 0
        parent_depth = depth(parent_id, stack | {entry_id})
        memo[entry_id] = None if parent_depth is None else parent_depth + 1
        return memo[entry_id]

    for entry_id in parents:
        depth(entry_id, set())
    return memo


def _relation_adjacency(graph: dict[str, Any]) -> tuple[dict[str, list[tuple[str, str]]], set[str]]:
    adjacency: dict[str, list[tuple[str, str]]] = {}
    dimensions: set[str] = set()
    for edge in graph.get("edges", []):
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        dimension = str(edge.get("dimension") or "relation")
        if not source or not target:
            continue
        dimensions.add(dimension)
        adjacency.setdefault(source, []).append((target, dimension))
        adjacency.setdefault(target, []).append((source, dimension))
    for values in adjacency.values():
        values.sort(key=lambda item: (item[1], item[0]))
    return adjacency, dimensions


def filter_for_instance(
    tree: dict[str, Any],
    graph: dict[str, Any],
    *,
    root_topic: str,
    dependency_depth: int,
) -> tuple[dict[str, Any], dict[str, int | None], dict[str, Any]]:
    relation_depth = max(0, min(MAX_RELATION_DEPTH, int(dependency_depth)))
    entries = _entries(tree)
    selectable = {item["id"] for item in topic_catalog(tree)}

    if root_topic == "all":
        base_ids = set(entries)
        root_name = "all"
    else:
        if root_topic not in entries:
            raise KeyError(f"Unknown projection root topic: {root_topic}")
        if root_topic not in selectable:
            raise KeyError(f"Projection root is not selectable: {root_topic}")
        base_ids = _containment_subtree(root_topic, entries)
        root_name = str(entries[root_topic].get("name") or root_topic)

    included = set(base_ids)
    adjacency, available_dimensions = _relation_adjacency(graph)
    frontier = deque((entry_id, 0) for entry_id in sorted(base_ids))
    seen_depth: dict[str, int] = {entry_id: 0 for entry_id in base_ids}
    reached_by_dimension: dict[str, int] = {}

    while frontier:
        current, depth = frontier.popleft()
        if depth >= relation_depth:
            continue
        for neighbor, dimension in adjacency.get(current, []):
            next_depth = depth + 1
            previous = seen_depth.get(neighbor)
            if previous is not None and previous <= next_depth:
                continue
            seen_depth[neighbor] = next_depth
            if neighbor not in included:
                reached_by_dimension[dimension] = reached_by_dimension.get(dimension, 0) + 1
            included.add(neighbor)
            frontier.append((neighbor, next_depth))

    nodes = [deepcopy(node) for node in graph.get("nodes", []) if str(node.get("id")) in included]
    edges = [
        deepcopy(edge) for edge in graph.get("edges", [])
        if str(edge.get("source")) in included and str(edge.get("target")) in included
    ]
    hierarchy_depths = _projection_hierarchy_depths(tree, included)
    metadata = {
        "root_topic": root_topic,
        "root_name": root_name,
        "dependency_depth": relation_depth,
        "relation_depth": relation_depth,
        "base_node_count": len(base_ids),
        "node_count": len(nodes),
        "relation_added_count": max(0, len(included) - len(base_ids)),
        "reached_by_dimension": reached_by_dimension,
        "available_dimensions": sorted(available_dimensions),
        "topic_rule": "explicit canonical identity plus explicit containment subtree",
        "expansion_rule": "all explicit documented graph relations; bidirectional discovery only",
        "inference": False,
    }
    return {
        "nodes": nodes,
        "edges": edges,
        "projection_root": root_topic,
        "projection_root_name": root_name,
        "projection_base_ids": sorted(base_ids),
        "projection_relation_depth": relation_depth,
    }, hierarchy_depths, metadata


def normalize_instance_spec(spec: dict[str, Any], index: int = 0) -> dict[str, Any]:
    instance_id = str(spec.get("id") or f"instance-{index + 1}").strip()
    if not instance_id:
        raise ValueError("Projection instance id must not be empty")
    name = str(spec.get("name") or instance_id).strip()
    if not name:
        raise ValueError("Projection instance name must not be empty")
    projection_style = str(spec.get("projection_style") or "atlas_2d").strip()
    valid_styles = {item["id"] for item in style_catalog()}
    if projection_style not in valid_styles:
        raise KeyError(f"Unknown projection style: {projection_style}")
    root_topic = str(spec.get("root_topic") or "IAM").strip()
    dependency_depth = max(0, min(MAX_RELATION_DEPTH, int(spec.get("dependency_depth", 0))))
    return {
        "id": instance_id,
        "name": name,
        "projection_style": projection_style,
        "root_topic": root_topic,
        "dependency_depth": dependency_depth,
    }
