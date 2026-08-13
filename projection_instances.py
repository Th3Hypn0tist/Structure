from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any

from canonical_projections import PROJECTIONS as CORE_PROJECTIONS
from canonical_projections_extra3d import PROJECTIONS as EXTRA_PROJECTIONS
from structure_reveal_projections import PROJECTIONS as STRUCTURE_REVEAL_PROJECTIONS
from topic_profiles import resolve_topic_profile, topic_base_ids

MAX_RELATION_DEPTH = 32
PRIMARY_ROOT_IDS = ("IAM", "AccessCore", "DWH")
PRIMARY_PROFILE_COMPAT = {"iam": "IAM", "accesscore": "AccessCore", "dwh": "DWH"}

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
    profile_topics = resolve_topic_profile(tree)
    if profile_topics:
        out: list[dict[str, Any]] = []
        for topic in profile_topics:
            item = deepcopy(topic)
            profile_id = str(item["id"])
            item["profile_id"] = profile_id
            item["id"] = PRIMARY_PROFILE_COMPAT.get(profile_id, profile_id)
            item["primary"] = profile_id in PRIMARY_PROFILE_COMPAT
            out.append(item)
        return out

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


def _absolute_hierarchy_depths(tree: dict[str, Any]) -> dict[str, int | None]:
    entries = _entries(tree)
    parents = {
        entry_id: (str(entry.get("parent_id")) if entry.get("parent_id") is not None else None)
        for entry_id, entry in entries.items()
    }
    memo: dict[str, int | None] = {}

    def depth(entry_id: str, stack: set[str]) -> int | None:
        if entry_id in memo:
            return memo[entry_id]
        if entry_id in stack:
            memo[entry_id] = None
            return None
        parent_id = parents.get(entry_id)
        if parent_id is None:
            memo[entry_id] = 0
            return 0
        if parent_id not in entries:
            memo[entry_id] = None
            return None
        parent_depth = depth(parent_id, stack | {entry_id})
        memo[entry_id] = None if parent_depth is None else parent_depth + 1
        return memo[entry_id]

    for entry_id in entries:
        depth(entry_id, set())
    return memo


def _projection_hierarchy_depths(tree: dict[str, Any], included: set[str]) -> dict[str, int | None]:
    absolute = _absolute_hierarchy_depths(tree)
    return {entry_id: absolute.get(entry_id) for entry_id in included}


def _profile_topic_id(root_topic: str) -> str:
    reverse = {wire: profile for profile, wire in PRIMARY_PROFILE_COMPAT.items()}
    return reverse.get(root_topic, root_topic)


def projection_base_ids(tree: dict[str, Any], root_topic: str) -> set[str]:
    entries = _entries(tree)
    if root_topic == "all":
        return set(entries)

    profile_id = _profile_topic_id(root_topic)
    profile_base = topic_base_ids(tree, profile_id)
    if profile_base is not None:
        return profile_base

    selectable = {item["id"] for item in topic_catalog(tree)}
    if root_topic not in entries:
        raise KeyError(f"Unknown projection root topic: {root_topic}")
    if root_topic not in selectable:
        raise KeyError(f"Projection root is not selectable: {root_topic}")
    return _containment_subtree(root_topic, entries)


def _topic_name(tree: dict[str, Any], root_topic: str) -> str:
    if root_topic == "all":
        return "all"
    for item in topic_catalog(tree):
        if item["id"] == root_topic:
            return str(item.get("label") or root_topic)
    entry = _entries(tree).get(root_topic)
    return str((entry or {}).get("name") or root_topic)


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
    external_visible_ids: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, int | None], dict[str, Any]]:
    relation_depth = max(0, min(MAX_RELATION_DEPTH, int(dependency_depth)))
    entries = _entries(tree)
    base_ids = projection_base_ids(tree, root_topic)
    root_name = _topic_name(tree, root_topic)
    external_visible_ids = set(external_visible_ids or set()) - base_ids

    included = set(base_ids)
    absolute_depths = _absolute_hierarchy_depths(tree)
    hierarchy_depths = {entry_id: absolute_depths.get(entry_id) for entry_id in base_ids}

    projection_generations: dict[str, int | None] = {
        entry_id: (depth + 1 if isinstance(depth, int) else None)
        for entry_id, depth in hierarchy_depths.items()
    }
    projection_depths: dict[str, int | None] = {
        entry_id: (generation - 1 if isinstance(generation, int) else None)
        for entry_id, generation in projection_generations.items()
    }
    projection_parent_ids: dict[str, str | None] = {}
    for entry_id in base_ids:
        raw_parent = entries[entry_id].get("parent_id")
        parent_id = str(raw_parent) if raw_parent is not None else None
        projection_parent_ids[entry_id] = parent_id if parent_id in base_ids else None

    adjacency, available_dimensions = _relation_adjacency(graph)
    frontier = deque(
        (entry_id, 0, projection_generations.get(entry_id))
        for entry_id in sorted(base_ids)
    )
    best_hops: dict[str, int] = {entry_id: 0 for entry_id in base_ids}
    reached_by_dimension: dict[str, int] = {}
    external_references: list[dict[str, Any]] = []
    external_ref_keys: set[tuple[str, str, str]] = set()

    while frontier:
        current, hops, generation = frontier.popleft()
        if hops >= relation_depth:
            continue
        for neighbor, relation_dimension in adjacency.get(current, []):
            next_hops = hops + 1
            next_generation = generation + 1 if isinstance(generation, int) else None

            if neighbor in base_ids:
                continue

            if neighbor in external_visible_ids:
                key = (current, neighbor, relation_dimension)
                if key not in external_ref_keys:
                    external_ref_keys.add(key)
                    external_references.append({
                        "source_id": current,
                        "target_id": neighbor,
                        "dimension": relation_dimension,
                        "relation_hops": next_hops,
                        "projection_generation": next_generation,
                        "projection_parent_id": current,
                        "recursion": "stopped_at_existing_scene_identity",
                    })
                continue

            previous_hops = best_hops.get(neighbor)
            if previous_hops is not None and previous_hops <= next_hops:
                continue

            first_reach = neighbor not in included
            best_hops[neighbor] = next_hops
            projection_generations[neighbor] = next_generation
            projection_depths[neighbor] = next_generation - 1 if isinstance(next_generation, int) else None
            projection_parent_ids[neighbor] = current
            included.add(neighbor)
            if first_reach:
                reached_by_dimension[relation_dimension] = reached_by_dimension.get(relation_dimension, 0) + 1
            frontier.append((neighbor, next_hops, next_generation))

    hierarchy_depths = _projection_hierarchy_depths(tree, included)
    nodes = []
    for node in graph.get("nodes", []):
        node_id = str(node.get("id"))
        if node_id not in included:
            continue
        projected_node = deepcopy(node)
        projected_node["hierarchy_depth"] = hierarchy_depths.get(node_id)
        projected_node["projection_depth"] = projection_depths.get(node_id)
        projected_node["projection_generation"] = projection_generations.get(node_id)
        projected_node["projection_parent_id"] = projection_parent_ids.get(node_id)
        projected_node["relation_depth"] = best_hops.get(node_id, 0)
        nodes.append(projected_node)

    edges = [
        deepcopy(edge) for edge in graph.get("edges", [])
        if str(edge.get("source")) in included and str(edge.get("target")) in included
    ]
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
        "external_reference_count": len(external_references),
        "external_reference_ids": sorted({item["target_id"] for item in external_references}),
        "external_references": external_references,
        "topic_rule": "replaceable topic profile when present; exact explicit canonical identity resolution only; canonical hierarchy remains authoritative",
        "expansion_rule": "all explicit documented graph relations; bidirectional discovery only",
        "projection_depth_rule": "recursive parent generation; generation 1 is odd; each explicit relation hop advances one generation",
        "projection_parent_rule": "base nodes use explicit StructureTree parent_id; relation-expanded nodes use the explicit recursion predecessor as presentation parent",
        "existing_identity_rule": "relation-expanded identity already visible/reserved in another projection is referenced, not duplicated, and recursion stops there",
        "projection_depth_semantic_authority": False,
        "projection_parent_semantic_authority": False,
        "topic_profile_semantic_authority": False,
        "inference": False,
    }
    return {
        "nodes": nodes,
        "edges": edges,
        "projection_root": root_topic,
        "projection_root_name": root_name,
        "projection_base_ids": sorted(base_ids),
        "projection_relation_depth": relation_depth,
        "projection_external_references": external_references,
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
        "master": bool(spec.get("master", False)),
        "projection_style": projection_style,
        "projection_dimension": projection_dimension,
        "projection_generator": projection_generator,
        "root_topic": root_topic,
        "dependency_depth": dependency_depth,
    }
