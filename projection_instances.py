from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any

from canonical_projections import PROJECTIONS as CORE_PROJECTIONS
from canonical_projections_extra3d import PROJECTIONS as EXTRA_PROJECTIONS

MAX_DEPENDENCY_DEPTH = 32
TOPIC_PREFIX = "canonical/json/"

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
}


def style_catalog() -> list[dict[str, Any]]:
    merged = {**CORE_PROJECTIONS, **EXTRA_PROJECTIONS}
    out: list[dict[str, Any]] = []
    for style_id, meta in merged.items():
        out.append({
            "id": style_id,
            "label": STYLE_LABELS.get(style_id, meta.get("title") or style_id),
            "dimension": meta.get("dimension"),
            "kind": meta.get("kind"),
        })
    return sorted(out, key=lambda item: (str(item.get("dimension")), str(item.get("label"))))


def topic_from_path(path: Any) -> str | None:
    if not isinstance(path, str) or not path.startswith(TOPIC_PREFIX):
        return None
    rest = path[len(TOPIC_PREFIX):]
    if not rest or "/" not in rest:
        return None
    topic = rest.split("/", 1)[0].strip()
    return topic or None


def topic_catalog(tree: dict[str, Any]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for entry in tree.get("entries", []):
        topic = topic_from_path((entry.get("provenance") or {}).get("path"))
        if topic:
            counts[topic] = counts.get(topic, 0) + 1
    return [
        {"id": topic, "label": topic, "entry_count": counts[topic]}
        for topic in sorted(counts)
    ]


def _entry_topic(entry: dict[str, Any]) -> str | None:
    return topic_from_path((entry.get("provenance") or {}).get("path"))


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


def filter_for_instance(
    tree: dict[str, Any],
    graph: dict[str, Any],
    *,
    root_topic: str,
    dependency_depth: int,
) -> tuple[dict[str, Any], dict[str, int | None], dict[str, Any]]:
    """Build a projection-only graph subset.

    `root_topic` is an explicit StructureProjector convenience grouping derived
    from the first directory below canonical/json. It is projection state, not
    canonical semantic authority. Dependency expansion follows only explicit
    dependencies edges in their source -> target direction.
    """
    dependency_depth = max(0, min(MAX_DEPENDENCY_DEPTH, int(dependency_depth)))
    entries = {str(entry.get("id")): entry for entry in tree.get("entries", []) if entry.get("id") is not None}
    topics = {item["id"] for item in topic_catalog(tree)}
    if root_topic != "all" and root_topic not in topics:
        raise KeyError(f"Unknown projection root topic: {root_topic}")

    if root_topic == "all":
        base_ids = set(entries)
    else:
        base_ids = {entry_id for entry_id, entry in entries.items() if _entry_topic(entry) == root_topic}

    included = set(base_ids)
    dependency_edges = [
        edge for edge in graph.get("edges", [])
        if edge.get("dimension") == "dependencies"
    ]
    outgoing: dict[str, list[str]] = {}
    for edge in dependency_edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source and target:
            outgoing.setdefault(source, []).append(target)

    frontier = deque((entry_id, 0) for entry_id in sorted(base_ids))
    seen_depth: dict[str, int] = {entry_id: 0 for entry_id in base_ids}
    while frontier:
        current, depth = frontier.popleft()
        if depth >= dependency_depth:
            continue
        for target in sorted(outgoing.get(current, [])):
            next_depth = depth + 1
            previous = seen_depth.get(target)
            if previous is not None and previous <= next_depth:
                continue
            seen_depth[target] = next_depth
            included.add(target)
            frontier.append((target, next_depth))

    nodes = [deepcopy(node) for node in graph.get("nodes", []) if str(node.get("id")) in included]
    edges = [
        deepcopy(edge) for edge in graph.get("edges", [])
        if str(edge.get("source")) in included and str(edge.get("target")) in included
    ]
    hierarchy_depths = _projection_hierarchy_depths(tree, included)
    metadata = {
        "root_topic": root_topic,
        "dependency_depth": dependency_depth,
        "base_node_count": len(base_ids),
        "node_count": len(nodes),
        "dependency_added_count": max(0, len(included) - len(base_ids)),
        "topic_rule": "first directory below canonical/json; projection convenience only",
        "dependency_rule": "explicit dependencies source -> target only",
    }
    return {"nodes": nodes, "edges": edges}, hierarchy_depths, metadata


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
    root_topic = str(spec.get("root_topic") or "all").strip()
    dependency_depth = max(0, min(MAX_DEPENDENCY_DEPTH, int(spec.get("dependency_depth", 0))))
    return {
        "id": instance_id,
        "name": name,
        "projection_style": projection_style,
        "root_topic": root_topic,
        "dependency_depth": dependency_depth,
    }
