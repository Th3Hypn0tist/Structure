from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any

from topic_profiles import resolve_topic_profile, topic_base_ids

MAX_RELATION_DEPTH = 32


def _entries(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(e.get("id")): e for e in tree.get("entries", []) if e.get("id") is not None}


def _absolute_depths(tree: dict[str, Any]) -> dict[str, int | None]:
    entries = _entries(tree)
    memo: dict[str, int | None] = {}

    def resolve(entry_id: str, stack: set[str]) -> int | None:
        if entry_id in memo:
            return memo[entry_id]
        if entry_id in stack:
            memo[entry_id] = None
            return None
        parent = entries[entry_id].get("parent_id")
        if parent is None:
            memo[entry_id] = 0
            return 0
        parent_id = str(parent)
        if parent_id not in entries:
            memo[entry_id] = None
            return None
        depth = resolve(parent_id, stack | {entry_id})
        memo[entry_id] = None if depth is None else depth + 1
        return memo[entry_id]

    for entry_id in entries:
        resolve(entry_id, set())
    return memo


def filter_profile_topic(
    tree: dict[str, Any],
    graph: dict[str, Any],
    *,
    topic_id: str,
    relation_depth: int,
    external_visible_ids: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, int | None], dict[str, Any]]:
    base_ids = topic_base_ids(tree, topic_id)
    if base_ids is None:
        raise KeyError(topic_id)
    depth_limit = max(0, min(MAX_RELATION_DEPTH, int(relation_depth)))
    external = set(external_visible_ids or set()) - base_ids
    absolute = _absolute_depths(tree)
    entries = _entries(tree)

    generations = {node_id: (absolute[node_id] + 1 if isinstance(absolute.get(node_id), int) else None) for node_id in base_ids}
    projection_depths = {node_id: (g - 1 if isinstance(g, int) else None) for node_id, g in generations.items()}
    parents = {
        node_id: (
            str(entries[node_id].get("parent_id"))
            if entries[node_id].get("parent_id") is not None and str(entries[node_id].get("parent_id")) in base_ids
            else None
        )
        for node_id in base_ids
    }

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

    included = set(base_ids)
    best_hops = {node_id: 0 for node_id in base_ids}
    frontier = deque((node_id, 0, generations.get(node_id)) for node_id in sorted(base_ids))
    external_refs: list[dict[str, Any]] = []
    seen_external: set[tuple[str, str, str]] = set()
    reached: dict[str, int] = {}

    while frontier:
        current, hops, generation = frontier.popleft()
        if hops >= depth_limit:
            continue
        for neighbor, dimension in adjacency.get(current, []):
            next_hops = hops + 1
            next_generation = generation + 1 if isinstance(generation, int) else None
            if neighbor in base_ids:
                continue
            if neighbor in external:
                key = (current, neighbor, dimension)
                if key not in seen_external:
                    seen_external.add(key)
                    external_refs.append({
                        "source_id": current,
                        "target_id": neighbor,
                        "dimension": dimension,
                        "relation_hops": next_hops,
                        "projection_generation": next_generation,
                        "projection_parent_id": current,
                        "recursion": "stopped_at_existing_scene_identity",
                    })
                continue
            if best_hops.get(neighbor, depth_limit + 1) <= next_hops:
                continue
            best_hops[neighbor] = next_hops
            generations[neighbor] = next_generation
            projection_depths[neighbor] = next_generation - 1 if isinstance(next_generation, int) else None
            parents[neighbor] = current
            included.add(neighbor)
            reached[dimension] = reached.get(dimension, 0) + 1
            frontier.append((neighbor, next_hops, next_generation))

    hierarchy = {node_id: absolute.get(node_id) for node_id in included}
    nodes: list[dict[str, Any]] = []
    for node in graph.get("nodes", []):
        node_id = str(node.get("id"))
        if node_id not in included:
            continue
        item = deepcopy(node)
        item["hierarchy_depth"] = hierarchy.get(node_id)
        item["projection_depth"] = projection_depths.get(node_id)
        item["projection_generation"] = generations.get(node_id)
        item["projection_parent_id"] = parents.get(node_id)
        item["relation_depth"] = best_hops.get(node_id, 0)
        nodes.append(item)

    edges = [
        deepcopy(edge)
        for edge in graph.get("edges", [])
        if str(edge.get("source")) in included and str(edge.get("target")) in included
    ]
    topic = next(item for item in resolve_topic_profile(tree) if item["id"] == topic_id)
    metadata = {
        "root_topic": topic_id,
        "root_name": topic["label"],
        "dependency_depth": depth_limit,
        "relation_depth": depth_limit,
        "base_node_count": len(base_ids),
        "node_count": len(nodes),
        "relation_added_count": max(0, len(included) - len(base_ids)),
        "reached_by_dimension": reached,
        "available_dimensions": sorted(dimensions),
        "external_reference_count": len(external_refs),
        "external_reference_ids": sorted({x["target_id"] for x in external_refs}),
        "external_references": external_refs,
        "topic_rule": "replaceable software topic profile selects exact canonical identities; canonical hierarchy and relations remain authoritative",
        "profile_membership_semantic_authority": False,
        "inference": False,
    }
    return {
        "nodes": nodes,
        "edges": edges,
        "projection_root": topic_id,
        "projection_root_name": topic["label"],
        "projection_base_ids": sorted(base_ids),
        "projection_relation_depth": depth_limit,
        "projection_external_references": external_refs,
    }, hierarchy, metadata
