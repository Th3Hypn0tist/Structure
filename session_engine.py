from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from event_trace import build_event_surface, event_catalog
from input_modules.canonical import read as read_canonical
from projection_instances import filter_for_instance, topic_catalog
from scene_composer import compose_projection_instances
from semantic_projection_styles import (
    PROJECTION_STYLES,
    STRUCTURAL_DIMENSION_STYLES,
    impact_graph,
    projection_style_catalog,
    structural_dimension_graph,
)
from semantic_visual_projections import resolve_visual_style, style_catalog
from source_selection import load_source
from structure_tree import tree_to_graph


DEFAULT_MASTER_ID = "master-1"


def _source_identity(spec: dict[str, Any], index: int) -> str:
    value = str(spec.get("id") or spec.get("master_id") or f"master-{index + 1}").strip()
    if not value:
        raise ValueError("Source/master id must not be empty")
    return value


def normalize_sources(body: dict[str, Any]) -> list[dict[str, Any]]:
    raw_sources = body.get("sources")
    if isinstance(raw_sources, list):
        if not raw_sources or not all(isinstance(item, dict) for item in raw_sources):
            raise ValueError("sources must be a non-empty array of objects")
        out = []
        for index, item in enumerate(raw_sources):
            master_id = _source_identity(item, index)
            source_spec = item.get("source") if isinstance(item.get("source"), dict) else {
                key: value for key, value in item.items() if key not in {"id", "master_id", "name"}
            }
            out.append({"id": master_id, "name": str(item.get("name") or master_id), "source": source_spec})
        return out

    source = body.get("source")
    if not isinstance(source, dict):
        source = {
            "type": "github",
            "repo": str(body.get("repo") or "Th3Hypn0tist/AIGMos_docs"),
            "branch": str(body.get("branch") or "main"),
        }
    return [{"id": DEFAULT_MASTER_ID, "name": DEFAULT_MASTER_ID, "source": source}]


def load_masters(source_specs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    masters: dict[str, dict[str, Any]] = {}
    for item in source_specs:
        master_id = item["id"]
        if master_id in masters:
            raise ValueError(f"Duplicate source/master id: {master_id}")
        snapshot = load_source(item["source"])
        tree = read_canonical(snapshot)
        masters[master_id] = {
            "id": master_id,
            "name": item.get("name") or master_id,
            "source_spec": deepcopy(item["source"]),
            "snapshot": snapshot,
            "tree": tree,
            "graph": tree_to_graph(tree),
        }
    return masters


def _scope_catalog(tree: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    entries = [entry for entry in tree.get("entries", []) if isinstance(entry, dict) and entry.get("id") is not None]
    flows = [flow for flow in tree.get("flows", []) if isinstance(flow, dict) and flow.get("id")]
    return {
        "topics": [{"id": "all", "label": "all", "entry_count": len(entries), "canonical_topic": False}] + topic_catalog(tree),
        "events": event_catalog(tree),
        "flows": [{"id": str(flow["id"]), "name": str(flow.get("name") or flow["id"]), "owner_ref": flow.get("owner_ref")} for flow in flows],
        "identities": [{"id": str(entry["id"]), "name": str(entry.get("name") or entry["id"]), "kind": entry.get("kind"), "type": entry.get("type")} for entry in entries],
    }


def master_catalog(master: dict[str, Any]) -> dict[str, Any]:
    tree = master["tree"]
    return {
        "id": master["id"],
        "name": master["name"],
        "source": tree.get("source", {}),
        "valid": bool(tree.get("valid")),
        "projectable": bool(tree.get("projectable")),
        "errors": deepcopy(tree.get("errors", [])),
        "scopes": _scope_catalog(tree),
    }


def session_catalog(masters: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "projection_styles": projection_style_catalog(),
        "visual_styles": style_catalog(),
        "dimensions": ["2d", "3d"],
        "defaults": {
            "semantic_projection_style": "topic",
            "visual_style": "atlas",
            "projection_dimension": "3d",
            "relation_depth": 0,
        },
        "masters": [master_catalog(master) for master in masters.values()],
        "rules": {
            "master": "a projection references exactly one source/master; one master may feed multiple projections",
            "projection_style": "semantic question asked of the master",
            "visual_style": "geometry only; it consumes the semantic projection graph and never changes semantic membership",
            "visual_dimension": "every visual style has native 2D and 3D generators",
            "cross_master_binding": "explicit only; never inferred by matching display names",
        },
    }


def _default_scope(master: dict[str, Any], semantic_style: str) -> tuple[str, str]:
    scopes = _scope_catalog(master["tree"])
    if semantic_style == "impact":
        events = scopes["events"]
        return "event", str(events[0]["id"]) if events else ""
    if semantic_style in STRUCTURAL_DIMENSION_STYLES:
        topics = [item for item in scopes["topics"] if item.get("canonical_topic")]
        if topics:
            return "topic", str(topics[0]["id"])
        identities = scopes["identities"]
        return "identity", str(identities[0]["id"]) if identities else ""
    topics = [item for item in scopes["topics"] if item.get("canonical_topic")]
    if topics:
        return "topic", str(topics[0]["id"])
    return "all", "all"


def _resolve_visual_projection(visual_input: str, dimension_input: Any) -> tuple[str, str, str]:
    requested_dimension = str(dimension_input).lower().strip() if dimension_input is not None else "3d"
    return resolve_visual_style(visual_input, requested_dimension)


def normalize_projection_instance(spec: dict[str, Any], index: int, masters: dict[str, dict[str, Any]]) -> dict[str, Any]:
    instance_id = str(spec.get("id") or f"projection-{index + 1}").strip()
    if not instance_id:
        raise ValueError("Projection instance id must not be empty")
    master_ref = str(spec.get("master_ref") or spec.get("source_ref") or next(iter(masters), "")).strip()
    if master_ref not in masters:
        raise KeyError(f"Unknown projection master/source: {master_ref}")

    semantic_input = str(spec.get("semantic_projection_style") or spec.get("projection_type") or spec.get("projection_style") or "topic").strip()
    if semantic_input in PROJECTION_STYLES:
        semantic_style = semantic_input
        visual_input = str(spec.get("visual_style") or "atlas").strip()
    else:
        semantic_style = "topic"
        visual_input = str(spec.get("visual_style") or semantic_input or "atlas").strip()

    semantic_spec = PROJECTION_STYLES.get(semantic_style)
    if semantic_spec is None:
        raise KeyError(f"Unknown semantic projection style: {semantic_style}")
    if not semantic_spec.get("implemented"):
        raise ValueError(f"Projection style is specified but not implemented yet: {semantic_style}")

    dimension_input = spec.get("projection_dimension") or spec.get("dimension")
    visual_style, dimension, generator = _resolve_visual_projection(visual_input, dimension_input)

    default_scope_type, default_scope_ref = _default_scope(masters[master_ref], semantic_style)
    scope_type = str(spec.get("scope_type") or ("topic" if spec.get("root_topic") else default_scope_type)).strip()
    scope_ref = str(spec.get("scope_ref") or spec.get("root_topic") or default_scope_ref).strip()
    if scope_type not in semantic_spec.get("scope_types", []):
        raise ValueError(f"Projection style {semantic_style} does not accept scope type {scope_type}")
    if not scope_ref:
        raise ValueError(f"Projection style {semantic_style} requires a scope_ref")

    relation_depth = max(0, min(32, int(spec.get("relation_depth", spec.get("dependency_depth", 0)))))
    impact_depth = max(0, min(64, int(spec.get("impact_depth", 32))))
    return {
        "id": instance_id,
        "name": str(spec.get("name") or instance_id),
        "master_ref": master_ref,
        "projection_style": semantic_style,
        "scope_type": scope_type,
        "scope_ref": scope_ref,
        "visual_style": visual_style,
        "projection_dimension": dimension,
        "projection_generator": generator,
        "relation_depth": relation_depth,
        "impact_depth": impact_depth,
        "transform": deepcopy(spec.get("transform")) if isinstance(spec.get("transform"), dict) else None,
    }


def _topic_projection(master: dict[str, Any], instance: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, int | None]]:
    tree, graph = master["tree"], master["graph"]
    root = instance["scope_ref"] if instance["scope_type"] == "topic" else "all"
    filtered, hierarchy_depths, metadata = filter_for_instance(
        tree,
        graph,
        root_topic=root,
        dependency_depth=instance["relation_depth"],
        external_visible_ids=set(),
    )
    metadata["projection_style"] = "topic"
    metadata["scope_type"] = instance["scope_type"]
    metadata["scope_ref"] = instance["scope_ref"]
    return filtered, metadata, hierarchy_depths


def _impact_projection(master: dict[str, Any], instance: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, int | None]]:
    projected, metadata = impact_graph(
        master["tree"],
        master["graph"],
        instance["scope_ref"],
        max_depth=instance["impact_depth"],
    )
    hierarchy_depths = {
        str(node.get("id")): int(node.get("impact_wave") or 0)
        for node in projected.get("nodes", [])
        if node.get("id") is not None
    }
    return projected, metadata, hierarchy_depths


def _structural_projection(master: dict[str, Any], instance: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, int | None]]:
    projected, metadata, hierarchy_depths = structural_dimension_graph(
        master["tree"],
        master["graph"],
        projection_style=instance["projection_style"],
        scope_type=instance["scope_type"],
        scope_ref=instance["scope_ref"],
        max_depth=instance["relation_depth"],
    )
    return projected, metadata, hierarchy_depths


def build_session_scene(
    masters: dict[str, dict[str, Any]],
    raw_instances: list[dict[str, Any]],
    visual_builder: Callable[[dict[str, Any], str], dict[str, Any]],
) -> dict[str, Any]:
    if not raw_instances:
        raise ValueError("At least one projection instance is required")
    instances = [normalize_projection_instance(spec, index, masters) for index, spec in enumerate(raw_instances)]
    ids = [item["id"] for item in instances]
    if len(ids) != len(set(ids)):
        raise ValueError("Projection instance ids must be unique")

    by_master: dict[str, list[dict[str, Any]]] = {}
    for instance in instances:
        master = masters[instance["master_ref"]]
        if instance["projection_style"] == "impact":
            semantic_graph, metadata, hierarchy_depths = _impact_projection(master, instance)
        elif instance["projection_style"] in STRUCTURAL_DIMENSION_STYLES:
            semantic_graph, metadata, hierarchy_depths = _structural_projection(master, instance)
        else:
            semantic_graph, metadata, hierarchy_depths = _topic_projection(master, instance)
        visual_projection = visual_builder(semantic_graph, instance["projection_generator"])
        by_master.setdefault(instance["master_ref"], []).append({
            "instance": {
                **instance,
                "root_topic": instance["scope_ref"],
                "dependency_depth": instance["relation_depth"],
                "projection_style": instance["visual_style"],
            },
            "projection": visual_projection,
            "hierarchy_depths": hierarchy_depths,
            "filter_metadata": metadata,
        })

    scenes: list[tuple[str, dict[str, Any]]] = []
    for master_ref, items in by_master.items():
        master = masters[master_ref]
        scene = compose_projection_instances(
            items,
            master["tree"],
            include_cross_projection_connections=True,
        )
        for obj in scene.get("objects", []):
            obj["master_ref"] = master_ref
            instance_id = str(obj.get("instance_id") or "")
            instance = next((item for item in instances if item["id"] == instance_id), None)
            if instance:
                obj["semantic_projection_style"] = instance["projection_style"]
                obj["scope_type"] = instance["scope_type"]
                obj["scope_ref"] = instance["scope_ref"]
                obj["visual_style"] = instance["visual_style"]
        scene["event_surface"] = build_event_surface(master["tree"])
        scenes.append((master_ref, scene))

    base_master_ref, base_scene = scenes[0]
    merged = deepcopy(base_scene)
    merged["objects"] = []
    merged["connections"] = []
    merged["connection_channels"] = {}
    merged["event_surfaces"] = {}
    for master_ref, scene in scenes:
        merged["objects"].extend(deepcopy(scene.get("objects", [])))
        merged["connections"].extend(deepcopy(scene.get("connections", [])))
        for key, value in scene.get("connection_channels", {}).items():
            merged["connection_channels"].setdefault(key, deepcopy(value))
        merged["event_surfaces"][master_ref] = deepcopy(scene.get("event_surface", {}))

    merged["event_surface"] = deepcopy(merged["event_surfaces"].get(base_master_ref, {}))
    merged["composition"] = {
        "master_count": len(masters),
        "projection_count": len(instances),
        "master_refs": list(masters),
        "projection_master_rule": "each projection references one master; masters may feed many projections",
        "cross_master_binding": "none unless explicitly provided by a future comparison/binding source",
        "cross_master_inference": False,
    }
    merged["validation_errors"] = []
    return {
        "scene": merged,
        "instances": instances,
        "catalog": session_catalog(masters),
        "masters": [master_catalog(master) for master in masters.values()],
    }


__all__ = [
    "normalize_sources",
    "load_masters",
    "master_catalog",
    "session_catalog",
    "normalize_projection_instance",
    "build_session_scene",
]
