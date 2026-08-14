from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from event_projection import build_event_projection
from event_trace import build_event_surface, event_catalog
from input_modules.canonical import read as read_canonical
from projection_model import (
    PROJECTION_BASES,
    apply_scope_style,
    compatible_projection_styles,
    normalize_projection_base,
    normalize_scope_style,
    projection_base_catalog,
    resolve_projection_style,
    scope_style_catalog,
)
from scene_composer import compose_projection_instances
from source_selection import load_source
from structural_projection import structural_base_graph
from structure_tree import tree_to_graph
from topic_index import topic_all_graph, topic_heading_catalog, topic_scope_graph


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
    headings = topic_heading_catalog(tree)
    return {
        "topics": [
            {
                "id": "all",
                "label": "all",
                "entry_count": len(headings),
                "heading_count": len(headings),
                "scope_semantics": "all_topic_headings_only",
            }
        ] + [
            {
                "id": str(item["id"]),
                "label": str(item.get("label") or item["id"]),
                "entry_count": int(item.get("entry_count") or 0),
                "topic_heading": True,
                "defined": bool(item.get("defined")),
                "unresolved": bool(item.get("unresolved")),
                "direct_topic_refs": deepcopy(item.get("direct_topic_refs", [])),
                "resolved_topic_refs": deepcopy(item.get("resolved_topic_refs", [])),
            }
            for item in headings
        ],
        "events": event_catalog(tree),
        "flows": [
            {"id": str(flow["id"]), "name": str(flow.get("name") or flow["id"]), "owner_ref": flow.get("owner_ref")}
            for flow in flows
        ],
        "identities": [
            {"id": str(entry["id"]), "name": str(entry.get("name") or entry["id"]), "kind": entry.get("kind"), "type": entry.get("type")}
            for entry in entries
        ],
    }


def master_catalog(master: dict[str, Any]) -> dict[str, Any]:
    tree = master["tree"]
    indexes = tree.get("indexes") if isinstance(tree.get("indexes"), dict) else {}
    topic_index = tree.get("topic_index") if isinstance(tree.get("topic_index"), dict) else {}
    return {
        "id": master["id"],
        "name": master["name"],
        "source": tree.get("source", {}),
        "valid": bool(tree.get("valid")),
        "projectable": bool(tree.get("projectable")),
        "errors": deepcopy(tree.get("errors", [])),
        "scopes": _scope_catalog(tree),
        "structure_tree_index": {
            "version": indexes.get("version"),
            "resolved_at": indexes.get("resolved_at"),
            "topic_heading_count": topic_index.get("heading_count", 0),
            "topic_unresolved_heading_count": topic_index.get("unresolved_heading_count", 0),
            "projection_reanalysis_required": False,
        },
    }


def _projection_style_catalog() -> list[dict[str, Any]]:
    by_style: dict[str, dict[str, Any]] = {}
    for base_id in PROJECTION_BASES:
        for style in compatible_projection_styles(base_id):
            item = by_style.setdefault(style["id"], {**style, "projection_bases": []})
            item["projection_bases"].append(base_id)
    return sorted(by_style.values(), key=lambda item: str(item.get("label") or item["id"]).lower())


def session_catalog(masters: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "projection_bases": projection_base_catalog(),
        "projection_styles": _projection_style_catalog(),
        "projection_styles_by_base": {
            base_id: compatible_projection_styles(base_id)
            for base_id in PROJECTION_BASES
        },
        "scope_styles": scope_style_catalog(),
        "dimensions": ["2d", "3d"],
        "defaults": {
            "projection_base": "map",
            "projection_style": PROJECTION_BASES["map"]["default_style"],
            "scope_type": "all",
            "scope_ref": "all",
            "scope_style": "semantic_roles",
            "projection_dimension": "3d",
            "relation_depth": 0,
        },
        "masters": [master_catalog(master) for master in masters.values()],
        "rules": {
            "master": "a projection references exactly one source/master; one master may feed multiple projections",
            "structure_tree": "reusable semantic topology and lookup indexes are resolved once at source import",
            "projection_base": "selects which already-resolved StructureTree semantic model is projected",
            "projection_style": "selects a geometry compatible with the projection base; it never changes semantic membership",
            "scope": "selects a subset of the projection base",
            "scope_style": "color/highlight only; it never changes nodes, edges, scope or causality",
            "topic_all": "map/all shows only pre-resolved Topic headings; details remain collapsed until a heading is selected",
            "dimension": "2D/3D is independent of projection base, projection style and scope style",
            "cross_master_binding": "explicit only; never inferred by matching display names",
        },
    }


def _default_scope(master: dict[str, Any], projection_base: str) -> tuple[str, str]:
    scopes = _scope_catalog(master["tree"])
    base = PROJECTION_BASES[projection_base]
    if projection_base == "map":
        return "all", "all"
    if projection_base == "event":
        events = scopes["events"]
        return "event", str(events[0]["id"]) if events else ""
    if "topic" in base["scope_types"]:
        topics = [item for item in scopes["topics"] if item.get("topic_heading")]
        if topics:
            return "topic", str(topics[0]["id"])
    identities = scopes["identities"]
    return "identity", str(identities[0]["id"]) if identities else ""


def _legacy_projection_base(spec: dict[str, Any]) -> str:
    if spec.get("projection_base") is not None:
        return normalize_projection_base(spec.get("projection_base"))
    old = spec.get("semantic_projection_style") or spec.get("projection_type")
    if old is not None:
        return normalize_projection_base(old)
    if spec.get("visual_style") is not None and spec.get("projection_style") is not None:
        return normalize_projection_base(spec.get("projection_style"))
    return "map"


def _legacy_projection_style(spec: dict[str, Any], projection_base: str) -> str:
    if spec.get("projection_base") is not None:
        return str(spec.get("projection_style") or PROJECTION_BASES[projection_base]["default_style"]).strip()
    if spec.get("visual_style") is not None:
        return str(spec.get("visual_style") or PROJECTION_BASES[projection_base]["default_style"]).strip()
    candidate = str(spec.get("projection_style") or "").strip()
    if candidate in PROJECTION_BASES:
        return str(PROJECTION_BASES[projection_base]["default_style"])
    return candidate or str(PROJECTION_BASES[projection_base]["default_style"])


def normalize_projection_instance(spec: dict[str, Any], index: int, masters: dict[str, dict[str, Any]]) -> dict[str, Any]:
    instance_id = str(spec.get("id") or f"projection-{index + 1}").strip()
    if not instance_id:
        raise ValueError("Projection instance id must not be empty")
    master_ref = str(spec.get("master_ref") or spec.get("source_ref") or next(iter(masters), "")).strip()
    if master_ref not in masters:
        raise KeyError(f"Unknown projection master/source: {master_ref}")

    projection_base = _legacy_projection_base(spec)
    base_spec = PROJECTION_BASES[projection_base]
    projection_style_input = _legacy_projection_style(spec, projection_base)
    dimension_input = spec.get("projection_dimension") or spec.get("dimension") or "3d"
    projection_style, dimension, generator = resolve_projection_style(projection_base, projection_style_input, dimension_input)
    scope_style = normalize_scope_style(spec.get("scope_style"))

    default_scope_type, default_scope_ref = _default_scope(masters[master_ref], projection_base)
    scope_type = str(spec.get("scope_type") or ("topic" if spec.get("root_topic") else default_scope_type)).strip()
    scope_ref = str(spec.get("scope_ref") or spec.get("root_topic") or default_scope_ref).strip()
    if scope_type not in base_spec["scope_types"]:
        raise ValueError(f"Projection base {projection_base} does not accept scope type {scope_type}")
    if not scope_ref:
        raise ValueError(f"Projection base {projection_base} requires a scope_ref")

    relation_depth = max(0, min(32, int(spec.get("relation_depth", spec.get("dependency_depth", 0)))))
    impact_depth = max(0, min(64, int(spec.get("impact_depth", 32))))
    return {
        "id": instance_id,
        "name": str(spec.get("name") or instance_id),
        "master_ref": master_ref,
        "projection_base": projection_base,
        "projection_style": projection_style,
        "scope_type": scope_type,
        "scope_ref": scope_ref,
        "scope_style": scope_style,
        "projection_dimension": dimension,
        "projection_generator": generator,
        "relation_depth": relation_depth,
        "impact_depth": impact_depth,
        "transform": deepcopy(spec.get("transform")) if isinstance(spec.get("transform"), dict) else None,
    }


def _map_projection(master: dict[str, Any], instance: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, int | None]]:
    tree, graph = master["tree"], master["graph"]
    if instance["scope_type"] == "all" or instance["scope_ref"] == "all":
        return topic_all_graph(tree)
    return topic_scope_graph(tree, graph, instance["scope_ref"], relation_depth=instance["relation_depth"])


def _event_projection(master: dict[str, Any], instance: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, int | None]]:
    return build_event_projection(master["tree"], master["graph"], instance["scope_ref"], max_depth=instance["impact_depth"])


def _structural_projection(master: dict[str, Any], instance: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, int | None]]:
    return structural_base_graph(
        master["tree"],
        master["graph"],
        projection_base=instance["projection_base"],
        scope_type=instance["scope_type"],
        scope_ref=instance["scope_ref"],
        max_depth=instance["relation_depth"],
    )


def _base_projection(master: dict[str, Any], instance: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, int | None]]:
    engine = PROJECTION_BASES[instance["projection_base"]]["engine"]
    if engine == "topic":
        projected, metadata, depths = _map_projection(master, instance)
    elif engine == "event":
        projected, metadata, depths = _event_projection(master, instance)
    elif engine == "structural":
        projected, metadata, depths = _structural_projection(master, instance)
    else:
        raise ValueError(f"Unsupported projection base engine: {engine}")
    metadata["projection_base"] = instance["projection_base"]
    metadata["scope_style"] = instance["scope_style"]
    return apply_scope_style(projected, instance["scope_style"]), metadata, depths


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
        semantic_graph, metadata, hierarchy_depths = _base_projection(master, instance)
        visual_projection = visual_builder(semantic_graph, instance["projection_generator"])
        by_master.setdefault(instance["master_ref"], []).append({
            "instance": {
                **instance,
                "root_topic": instance["scope_ref"],
                "dependency_depth": instance["relation_depth"],
            },
            "projection": visual_projection,
            "hierarchy_depths": hierarchy_depths,
            "filter_metadata": metadata,
        })

    scenes: list[tuple[str, dict[str, Any]]] = []
    for master_ref, items in by_master.items():
        master = masters[master_ref]
        scene = compose_projection_instances(items, master["tree"], include_cross_projection_connections=True)
        for obj in scene.get("objects", []):
            obj["master_ref"] = master_ref
            instance_id = str(obj.get("instance_id") or "")
            instance = next((item for item in instances if item["id"] == instance_id), None)
            if instance:
                obj["projection_base"] = instance["projection_base"]
                obj["projection_style"] = instance["projection_style"]
                obj["scope_type"] = instance["scope_type"]
                obj["scope_ref"] = instance["scope_ref"]
                obj["scope_style"] = instance["scope_style"]
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
        "structure_tree_indexes": "resolved_once_at_import",
        "projection_contract": "projection_base + projection_style + scope + scope_style + dimension",
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
