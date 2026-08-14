from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from event_projection import build_event_projection
from event_trace import build_event_surface, event_catalog
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
from session_cache import cached_semantic_surface, cached_visual_surface, load_cached_master
from structural_projection import structural_base_graph
from topic_index import topic_all_graph, topic_heading_catalog, topic_scope_graph


DEFAULT_MASTER_ID = "master-1"


def _source_identity(spec: dict[str, Any], index: int) -> str:
    value = str(spec.get("id") or f"master-{index + 1}").strip()
    if not value:
        raise ValueError("Source/master id must not be empty")
    return value


def normalize_sources(body: dict[str, Any]) -> list[dict[str, Any]]:
    raw_sources = body.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources or not all(isinstance(item, dict) for item in raw_sources):
        raise ValueError("sources must be a non-empty array of source/master objects")
    out = []
    for index, item in enumerate(raw_sources):
        master_id = _source_identity(item, index)
        source_spec = item.get("source")
        if not isinstance(source_spec, dict):
            raise ValueError(f"Source/master {master_id} requires source object")
        out.append({
            "id": master_id,
            "name": str(item.get("name") or master_id),
            "source": deepcopy(source_spec),
        })
    return out


def load_masters(source_specs: list[dict[str, Any]], *, refresh: bool = False) -> dict[str, dict[str, Any]]:
    masters: dict[str, dict[str, Any]] = {}
    for item in source_specs:
        master_id = str(item["id"])
        if master_id in masters:
            raise ValueError(f"Duplicate source/master id: {master_id}")
        masters[master_id] = load_cached_master(item, refresh=refresh)
    return masters


def _scope_catalog(tree: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    entries = [entry for entry in tree.get("entries", []) if isinstance(entry, dict) and entry.get("id") is not None]
    flows = [flow for flow in tree.get("flows", []) if isinstance(flow, dict) and flow.get("id")]
    headings = topic_heading_catalog(tree)
    return {
        "topics": [{
            "id": "all",
            "label": "all",
            "entry_count": len(headings),
            "heading_count": len(headings),
            "scope_semantics": "all_topic_headings_only",
        }] + [{
            "id": str(item["id"]),
            "label": str(item.get("label") or item["id"]),
            "entry_count": int(item.get("entry_count") or 0),
            "topic_heading": True,
            "defined": bool(item.get("defined")),
            "unresolved": bool(item.get("unresolved")),
            "direct_topic_refs": deepcopy(item.get("direct_topic_refs", [])),
            "resolved_topic_refs": deepcopy(item.get("resolved_topic_refs", [])),
        } for item in headings],
        "events": event_catalog(tree),
        "flows": [{
            "id": str(flow["id"]),
            "name": str(flow.get("name") or flow["id"]),
            "owner_ref": flow.get("owner_ref"),
        } for flow in flows],
        "identities": [{
            "id": str(entry["id"]),
            "name": str(entry.get("name") or entry["id"]),
            "kind": entry.get("kind"),
            "type": entry.get("type"),
        } for entry in entries],
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
        "source_cache_hit": bool(master.get("source_cache_hit")),
        "semantic_surface_cache_count": len(master.get("semantic_surfaces", {})),
        "visual_surface_cache_count": len(master.get("visual_surfaces", {})),
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
        "projection_styles_by_base": {base_id: compatible_projection_styles(base_id) for base_id in PROJECTION_BASES},
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
            "impact_depth": 32,
        },
        "masters": [master_catalog(master) for master in masters.values()],
        "rules": {
            "master": "source import and StructureTree resolution happen once per unchanged source",
            "structure_tree": "reusable semantic topology and lookup indexes are resolved once at source import",
            "projection_base": "selects an already-resolved StructureTree surface",
            "projection_style": "uses geometry native to the selected projection base",
            "scope": "selects a cached or cheaply sliced StructureTree surface",
            "scope_style": "color/highlight only; no server-side geometry rebuild is required",
            "topic_all": "map/all shows only pre-resolved Topic headings",
            "dimension": "2D/3D is independent of projection base and scope style",
            "cross_master_binding": "explicit only; never inferred by matching display names",
            "compatibility_aliases": False,
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


def normalize_projection_instance(spec: dict[str, Any], index: int, masters: dict[str, dict[str, Any]]) -> dict[str, Any]:
    instance_id = str(spec.get("id") or f"projection-{index + 1}").strip()
    if not instance_id:
        raise ValueError("Projection instance id must not be empty")
    master_ref = str(spec.get("master_ref") or next(iter(masters), "")).strip()
    if master_ref not in masters:
        raise KeyError(f"Unknown projection master/source: {master_ref}")

    projection_base = normalize_projection_base(spec.get("projection_base") or "map")
    base_spec = PROJECTION_BASES[projection_base]
    projection_style, dimension, generator = resolve_projection_style(
        projection_base,
        spec.get("projection_style") or base_spec["default_style"],
        spec.get("projection_dimension") or "3d",
    )
    scope_style = normalize_scope_style(spec.get("scope_style"))
    default_scope_type, default_scope_ref = _default_scope(masters[master_ref], projection_base)
    scope_type = str(spec.get("scope_type") or default_scope_type).strip()
    scope_ref = str(spec.get("scope_ref") or default_scope_ref).strip()
    if scope_type not in base_spec["scope_types"]:
        raise ValueError(f"Projection base {projection_base} does not accept scope type {scope_type}")
    if not scope_ref:
        raise ValueError(f"Projection base {projection_base} requires a scope_ref")

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
        "relation_depth": max(0, min(32, int(spec.get("relation_depth", 0)))),
        "impact_depth": max(0, min(64, int(spec.get("impact_depth", 32)))),
        "transform": deepcopy(spec.get("transform")) if isinstance(spec.get("transform"), dict) else None,
    }


def _semantic_cache_key(instance: dict[str, Any]) -> tuple[Any, ...]:
    depth = instance["impact_depth"] if instance["projection_base"] == "event" else instance["relation_depth"]
    return (instance["projection_base"], instance["scope_type"], instance["scope_ref"], depth)


def _build_uncached_base(master: dict[str, Any], instance: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, int | None]]:
    tree, graph = master["tree"], master["graph"]
    engine = PROJECTION_BASES[instance["projection_base"]]["engine"]
    if engine == "topic":
        if instance["scope_type"] == "all" or instance["scope_ref"] == "all":
            return topic_all_graph(tree)
        return topic_scope_graph(tree, graph, instance["scope_ref"], relation_depth=instance["relation_depth"])
    if engine == "event":
        return build_event_projection(tree, graph, instance["scope_ref"], max_depth=instance["impact_depth"])
    if engine == "structural":
        return structural_base_graph(
            tree,
            graph,
            projection_base=instance["projection_base"],
            scope_type=instance["scope_type"],
            scope_ref=instance["scope_ref"],
            max_depth=instance["relation_depth"],
        )
    raise ValueError(f"Unsupported projection base engine: {engine}")


def _base_projection(master: dict[str, Any], instance: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, int | None], bool]:
    key = _semantic_cache_key(instance)
    projected, metadata, depths, hit = cached_semantic_surface(master, key, lambda: _build_uncached_base(master, instance))
    metadata["projection_base"] = instance["projection_base"]
    metadata["semantic_surface_cache_hit"] = hit
    return projected, metadata, depths, hit


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
        semantic_graph, metadata, hierarchy_depths, semantic_hit = _base_projection(master, instance)
        semantic_key = _semantic_cache_key(instance)
        visual_key = (*semantic_key, instance["projection_generator"])
        visual_projection, visual_hit = cached_visual_surface(
            master,
            visual_key,
            lambda: visual_builder(semantic_graph, instance["projection_generator"]),
        )
        visual_projection = apply_scope_style(visual_projection, instance["scope_style"])
        metadata.update({
            "scope_style": instance["scope_style"],
            "visual_surface_cache_hit": visual_hit,
            "server_reanalysis": not semantic_hit,
            "server_relayout": not visual_hit,
        })
        by_master.setdefault(instance["master_ref"], []).append({
            "instance": instance,
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
        "projection_surfaces": "cached_after_first_materialization",
        "projection_contract": "projection_base + projection_style + scope + scope_style + projection_dimension",
        "compatibility_aliases": False,
        "cross_master_binding": "none unless explicitly provided by a comparison/binding source",
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
