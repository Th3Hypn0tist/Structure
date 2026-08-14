from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any

from canonical_projections import PROJECTIONS as CORE_PROJECTIONS
from canonical_projections_extra3d import PROJECTIONS as EXTRA_PROJECTIONS
from structure_reveal_projections import PROJECTIONS as STRUCTURE_REVEAL_PROJECTIONS

MAX_RELATION_DEPTH = 32

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


def _topics(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(topic.get("id")): topic
        for topic in tree.get("topics", [])
        if isinstance(topic, dict) and topic.get("id")
    }


def _topic_descendants(topic_id: str, topics: dict[str, dict[str, Any]]) -> set[str]:
    seen: set[str] = set()
    queue = deque([topic_id])
    while queue:
        current = queue.popleft()
        if current in seen or current not in topics:
            continue
        seen.add(current)
        queue.extend(str(ref) for ref in topics[current].get("child_topic_refs", []))
    return seen


def _flow_surface_ids(tree: dict[str, Any], flow_ids: set[str]) -> set[str]:
    entries = _entries(tree)
    out: set[str] = set()
    by_flow = {
        str(flow.get("id")): flow
        for flow in tree.get("flows", [])
        if isinstance(flow, dict) and flow.get("id")
    }
    queue = deque(sorted(flow_ids))
    seen_flows: set[str] = set()
    while queue:
        flow_id = queue.popleft()
        if flow_id in seen_flows:
            continue
        seen_flows.add(flow_id)
        flow = by_flow.get(flow_id)
        if flow is None:
            continue
        owner = flow.get("owner_ref")
        if isinstance(owner, str) and owner in entries:
            out.add(owner)
        for step in flow.get("steps", []):
            if not isinstance(step, dict):
                continue
            for field in ("actor_ref", "action_ref", "data_ref", "target_ref", "cause_ref", "condition_ref", "payload_ref"):
                ref = step.get(field)
                if isinstance(ref, str) and ref in entries:
                    out.add(ref)
            for field in ("result_refs", "error_refs"):
                for ref in step.get(field, []):
                    if isinstance(ref, str) and ref in entries:
                        out.add(ref)
            queue.extend(str(ref) for ref in step.get("subflow_refs", []) if isinstance(ref, str))
    return out


def _topic_surface_ids(tree: dict[str, Any], topic_id: str) -> set[str]:
    entries = _entries(tree)
    topics = _topics(tree)
    if topic_id not in topics:
        return set()

    selected_topics = _topic_descendants(topic_id, topics)
    out: set[str] = set()
    flow_ids: set[str] = set()
    relation_ids: set[str] = set()

    for selected_id in selected_topics:
        topic = topics[selected_id]
        for field in ("member_refs", "operation_refs", "event_refs", "resolved_grouping_member_refs"):
            out.update(str(ref) for ref in topic.get(field, []) if str(ref) in entries)
        composed = topic.get("composed_trace_surface") if isinstance(topic.get("composed_trace_surface"), dict) else {}
        for field in ("member_refs", "operation_refs", "event_refs"):
            out.update(str(ref) for ref in composed.get(field, []) if str(ref) in entries)
        flow_ids.update(str(ref) for ref in topic.get("flow_refs", []))
        flow_ids.update(str(ref) for ref in composed.get("flow_refs", []))
        relation_ids.update(str(ref) for ref in topic.get("relation_refs", []))
        relation_ids.update(str(ref) for ref in composed.get("relation_refs", []))

    out.update(_flow_surface_ids(tree, flow_ids))
    for link in tree.get("links", []):
        if not isinstance(link, dict) or str(link.get("id") or "") not in relation_ids:
            continue
        for field in ("source_id", "target_id"):
            ref = link.get(field)
            if isinstance(ref, str) and ref in entries:
                out.add(ref)
    return out


def topic_catalog(tree: dict[str, Any]) -> list[dict[str, Any]]:
    topics = _topics(tree)
    if topics:
        out: list[dict[str, Any]] = []
        for topic_id, topic in topics.items():
            surface = _topic_surface_ids(tree, topic_id)
            out.append({
                "id": topic_id,
                "label": str(topic.get("name") or topic_id),
                "purpose": str(topic.get("purpose") or ""),
                "owner_ref": topic.get("owner_ref"),
                "container_topic_ref": topic.get("container_topic_ref"),
                "parent_topic_refs": deepcopy(topic.get("parent_topic_refs", [])),
                "composed_topic_refs": deepcopy(topic.get("composed_topic_refs", [])),
                "resolved_ancestor_topic_refs": deepcopy(topic.get("resolved_ancestor_topic_refs", [])),
                "resolved_component_topic_refs": deepcopy(topic.get("resolved_component_topic_refs", [])),
                "child_topic_refs": deepcopy(topic.get("child_topic_refs", [])),
                "entry_count": len(surface),
                "projection_base_ids": sorted(surface),
                "canonical_topic": True,
                "semantic_authority": False,
            })
        return sorted(out, key=lambda item: (str(item.get("label") or "").lower(), str(item["id"])))

    # Pre-1.4 compatibility is generic and uses explicit semantic roots only.
    entries = _entries(tree)
    roots = sorted(
        (entry_id for entry_id, entry in entries.items() if entry.get("parent_id") is None),
        key=lambda entry_id: str(entries[entry_id].get("name") or entry_id).lower(),
    )
    return [
        {
            "id": entry_id,
            "label": str(entries[entry_id].get("name") or entry_id),
            "entry_count": len(_containment_subtree(entry_id, entries)),
            "canonical_topic": False,
            "legacy_semantic_root": True,
        }
        for entry_id in roots
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


def projection_base_ids(tree: dict[str, Any], root_topic: str) -> set[str]:
    entries = _entries(tree)
    if root_topic == "all":
        return set(entries)

    topics = _topics(tree)
    if topics:
        if root_topic not in topics:
            raise KeyError(f"Unknown canonical Topic: {root_topic}")
        return _topic_surface_ids(tree, root_topic)

    selectable = {item["id"] for item in topic_catalog(tree)}
    if root_topic not in entries:
        raise KeyError(f"Unknown projection root: {root_topic}")
    if root_topic not in selectable:
        raise KeyError(f"Projection root is not selectable: {root_topic}")
    return _containment_subtree(root_topic, entries)


def _topic_name(tree: dict[str, Any], root_topic: str) -> str:
    if root_topic == "all":
        return "all"
    for item in topic_catalog(tree):
        if item["id"] == root_topic:
            return str(item.get("label") or root_topic)
    return root_topic


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
    frontier = deque((entry_id, 0, projection_generations.get(entry_id)) for entry_id in sorted(base_ids))
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
        "topic_rule": "Canonical Contract topics[] only when present; grouping, inheritance and composition remain non-semantic projection surfaces",
        "expansion_rule": "all explicit documented graph relations; bidirectional discovery only",
        "projection_depth_rule": "recursive parent generation; generation 1 is odd; each explicit relation hop advances one generation",
        "projection_parent_rule": "base nodes use explicit StructureTree parent_id; relation-expanded nodes use the explicit recursion predecessor as presentation parent",
        "existing_identity_rule": "relation-expanded identity already visible/reserved in another projection is referenced, not duplicated, and recursion stops there",
        "projection_depth_semantic_authority": False,
        "projection_parent_semantic_authority": False,
        "topic_semantic_authority": False,
        "topic_inheritance_implies_structure": False,
        "topic_composition_implies_structure": False,
        "topic_composition_implies_causality": False,
        "software_specific_topic_heuristics": False,
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

    root_topic = str(spec.get("root_topic") or "all").strip()
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
