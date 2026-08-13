from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any

from canonical_projections import PROJECTIONS as CORE_PROJECTIONS
from canonical_projections_extra3d import PROJECTIONS as EXTRA_PROJECTIONS
from structure_reveal_projections import PROJECTIONS as STRUCTURE_REVEAL_PROJECTIONS

MAX_RELATION_DEPTH = 32
PRIMARY_ROOT_IDS = ("IAM", "AccessCore", "DWH")

STYLE_FAMILIES: dict[str, dict[str, Any]] = {
    "atlas": {"label": "Atlas", "variants": {"2d": "atlas_2d", "3d": "atlas_3d"}},
    "map": {"label": "Map", "variants": {"2d": "relation_web_2d", "3d": "relation_web_3d"}},
    "matrix": {"label": "Matrix", "variants": {"2d": "adjacency_matrix_2d", "3d": "adjacency_matrix_3d"}},
    "lifecycle_lanes": {"label": "Lifecycle Lanes", "variants": {"2d": "lifecycle_lanes_2d", "3d": "lifecycle_lanes_3d"}},
    "dependency_flow": {"label": "Dependency Flow", "variants": {"2d": "dependency_flow_2d", "3d": "dependency_flow_3d"}},
    "galaxy": {"label": "Galaxy", "variants": {"3d": "semantic_galaxy_3d"}},
    "role_layers": {"label": "Role Layers", "variants": {"3d": "role_layers_3d"}},
    "dependency_tower": {"label": "Dependency Tower", "variants": {"3d": "dependency_tower_3d"}},
    "authority_space": {"label": "Authority Space", "variants": {"3d": "authority_space_3d"}},
    "relation_orbits": {"label": "Relation Orbits", "variants": {"3d": "relation_orbits_3d"}},
    "hierarchy_tree": {"label": "Hierarchy Tree", "variants": {"2d": "hierarchy_tree_2d"}},
    "relation_generations": {"label": "Relation Generations", "variants": {"2d": "relation_generations_2d"}},
    "component_islands": {"label": "Component Islands", "variants": {"2d": "component_islands_2d"}},
    "relation_shells": {"label": "Relation Shells", "variants": {"3d": "relation_shells_3d"}},
    "structure_spine": {"label": "Structure Spine", "variants": {"3d": "structure_spine_3d"}},
}


def _generator_catalog() -> dict[str, dict[str, Any]]:
    return {**CORE_PROJECTIONS, **EXTRA_PROJECTIONS, **STRUCTURE_REVEAL_PROJECTIONS}


def style_catalog() -> list[dict[str, Any]]:
    """Return one clean user-facing projection-style list.

    2D/3D is a separate selection. `variants` maps the user-facing style and
    dimension to the internal projection generator id. Missing variants remain
    missing; StructureProjector never substitutes an unavailable dimension.
    """
    generators = _generator_catalog()
    out: list[dict[str, Any]] = []
    for style_id, spec in STYLE_FAMILIES.items():
        variants = {
            dimension: generator_id
            for dimension, generator_id in spec["variants"].items()
            if generator_id in generators
        }
        if not variants:
            continue
        kinds = sorted({str(generators[generator_id].get("kind") or "") for generator_id in variants.values()})
        out.append({
            "id": style_id,
            "label": spec["label"],
            "dimensions": [dimension for dimension in ("2d", "3d") if dimension in variants],
            "variants": variants,
            "kind": kinds[0] if len(kinds) == 1 else "projection_style",
        })
    return sorted(out, key=lambda item: str(item["label"]).lower())


def resolve_projection_style(style: str, dimension: str | None = None) -> tuple[str, str, str]:
    """Resolve user-facing style + dimension to an internal generator id.

    Exact legacy generator ids are accepted for compatibility. When dimension
    is omitted, 2D is preferred only when that style explicitly provides 2D;
    otherwise its sole/3D variant is used. No unavailable variant is guessed.
    """
    style = str(style or "atlas").strip()
    dimension = str(dimension).lower().strip() if dimension is not None else None
    generators = _generator_catalog()

    if style in generators:
        for family_id, family in STYLE_FAMILIES.items():
            for variant_dimension, generator_id in family["variants"].items():
                if generator_id == style:
                    if dimension is not None and dimension != variant_dimension:
                        requested = family["variants"].get(dimension)
                        if requested is None or requested not in generators:
                            raise KeyError(f"Projection style {family_id} has no {dimension.upper()} variant")
                        return family_id, dimension, requested
                    return family_id, variant_dimension, generator_id
        raise KeyError(f"Projection generator has no style family: {style}")

    family = STYLE_FAMILIES.get(style)
    if family is None:
        raise KeyError(f"Unknown projection style: {style}")
    variants = {d: gid for d, gid in family["variants"].items() if gid in generators}
    if not variants:
        raise KeyError(f"Projection style has no available generator: {style}")

    if dimension is None:
        dimension = "2d" if "2d" in variants else "3d" if "3d" in variants else next(iter(variants))
    if dimension not in {"2d", "3d"}:
        raise KeyError(f"Unsupported projection dimension: {dimension}")
    generator = variants.get(dimension)
    if generator is None:
        raise KeyError(f"Projection style {style} has no {dimension.upper()} variant")
    return style, dimension, generator


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
        relation_dimension = str(edge.get("dimension") or "relation")
        if not source or not target:
            continue
        dimensions.add(relation_dimension)
        adjacency.setdefault(source, []).append((target, relation_dimension))
        adjacency.setdefault(target, []).append((source, relation_dimension))
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
        for neighbor, relation_dimension in adjacency.get(current, []):
            next_depth = depth + 1
            previous = seen_depth.get(neighbor)
            if previous is not None and previous <= next_depth:
                continue
            seen_depth[neighbor] = next_depth
            if neighbor not in included:
                reached_by_dimension[relation_dimension] = reached_by_dimension.get(relation_dimension, 0) + 1
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

    style_input = str(spec.get("projection_style") or "atlas").strip()
    dimension_input = spec.get("projection_dimension")
    projection_style, projection_dimension, projection_generator = resolve_projection_style(style_input, dimension_input)

    root_topic = str(spec.get("root_topic") or "IAM").strip()
    dependency_depth = max(0, min(MAX_RELATION_DEPTH, int(spec.get("dependency_depth", 0))))
    return {
        "id": instance_id,
        "name": name,
        "projection_style": projection_style,
        "projection_dimension": projection_dimension,
        "projection_generator": projection_generator,
        "root_topic": root_topic,
        "dependency_depth": dependency_depth,
    }
