from __future__ import annotations

from copy import deepcopy
from typing import Any

from scene_composer import compose_projection_instances
from session_cache import cached_semantic_surface, cached_visual_surface, load_cached_master
from topic_index import topic_all_graph, topic_heading_catalog, topic_scope_graph
from topic_projection import (
    PROJECTION_BASE,
    PROJECTIONS,
    apply_scope_style,
    build_topic_visual,
    normalize_projection_base,
    normalize_scope_style,
    projection_base_catalog,
    projection_style_catalog,
    projection_styles_by_base,
    resolve_projection_style,
    scope_style_catalog,
)


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


def _topic_scope_catalog(tree: dict[str, Any]) -> list[dict[str, Any]]:
    topic_index = tree.get("topic_index") if isinstance(tree.get("topic_index"), dict) else {}
    headings = topic_heading_catalog(tree)
    scopes = [{
        "id": "all",
        "label": "all",
        "scope_type": "all",
        "main_heading_count": int(topic_index.get("main_heading_count") or 0),
        "available_heading_count": len(headings),
    }]
    for item in headings:
        scopes.append({
            "id": str(item["id"]),
            "label": str(item.get("label") or item["id"]),
            "scope_type": "topic",
            "heading_depth": int(item.get("heading_depth") or 0),
            "main_heading": bool(item.get("main_heading")),
            "entry_count": int(item.get("entry_count") or 0),
            "defined": bool(item.get("defined")),
            "unresolved": bool(item.get("unresolved")),
            "parent_heading_refs": deepcopy(item.get("parent_heading_refs", [])),
            "direct_topic_refs": deepcopy(item.get("direct_topic_refs", [])),
        })
    return scopes


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
        "scopes": {
            "topics": _topic_scope_catalog(tree),
        },
        "structure_tree_index": {
            "version": indexes.get("version"),
            "resolved_at": indexes.get("resolved_at"),
            "topic_index_version": topic_index.get("version"),
            "topic_heading_count": topic_index.get("heading_count", 0),
            "topic_main_heading_count": topic_index.get("main_heading_count", 0),
            "topic_unresolved_heading_count": topic_index.get("unresolved_heading_count", 0),
            "projection_reanalysis_required": False,
        },
    }


def session_catalog(masters: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "projection_bases": projection_base_catalog(),
        "projection_styles": projection_style_catalog(),
        "projection_styles_by_base": projection_styles_by_base(),
        "scope_styles": scope_style_catalog(),
        "dimensions": ["2d", "3d"],
        "defaults": {
            "projection_base": "topic",
            "projection_style": "atlas",
            "scope_type": "all",
            "scope_ref": "all",
            "scope_style": "semantic_roles",
            "projection_dimension": "3d",
        },
        "masters": [master_catalog(master) for master in masters.values()],
        "rules": {
            "projection_types": "Topic only",
            "master": "source import and StructureTree resolution happen once per unchanged source",
            "structure_tree": "Topic topology and reusable indexes are resolved once at source import",
            "topic_scope": "scope is all or one pre-resolved Topic heading",
            "topic_all": "all renders only the Topic index main-heading surface",
            "projection_style": "Atlas is the only active Topic presentation while Topic semantics are rebuilt from first principles",
            "scope_style": "color/highlight only; it never changes Topic membership",
            "dimension": "2D/3D changes geometry only",
            "compatibility_aliases": False,
        },
    }


def _scope_ids(master: dict[str, Any]) -> set[str]:
    return {str(item["id"]) for item in _topic_scope_catalog(master["tree"])}


def normalize_projection_instance(spec: dict[str, Any], index: int, masters: dict[str, dict[str, Any]]) -> dict[str, Any]:
    instance_id = str(spec.get("id") or f"projection-{index + 1}").strip()
    if not instance_id:
        raise ValueError("Projection instance id must not be empty")

    master_ref = str(spec.get("master_ref") or next(iter(masters), "")).strip()
    if master_ref not in masters:
        raise KeyError(f"Unknown projection master/source: {master_ref}")

    projection_base = normalize_projection_base(spec.get("projection_base") or "topic")
    projection_style, dimension, generator = resolve_projection_style(
        spec.get("projection_style") or "atlas",
        spec.get("projection_dimension") or "3d",
    )
    scope_style = normalize_scope_style(spec.get("scope_style"))

    scope_ref = str(spec.get("scope_ref") or "all").strip()
    if scope_ref not in _scope_ids(masters[master_ref]):
        raise KeyError(f"Unknown Topic scope: {scope_ref}")
    scope_type = "all" if scope_ref == "all" else "topic"
    supplied_scope_type = spec.get("scope_type")
    if supplied_scope_type is not None and str(supplied_scope_type).strip() != scope_type:
        raise ValueError(f"Topic scope {scope_ref} requires scope_type={scope_type}")

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
        "transform": deepcopy(spec.get("transform")) if isinstance(spec.get("transform"), dict) else None,
    }


def _semantic_cache_key(instance: dict[str, Any]) -> tuple[Any, ...]:
    return ("topic", instance["scope_ref"])


def _build_topic_surface(master: dict[str, Any], instance: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, int | None]]:
    tree = master["tree"]
    if instance["scope_ref"] == "all":
        return topic_all_graph(tree)
    return topic_scope_graph(tree, master["graph"], instance["scope_ref"], relation_depth=0)


def _semantic_surface(master: dict[str, Any], instance: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, int | None], bool]:
    key = _semantic_cache_key(instance)
    projected, metadata, depths, hit = cached_semantic_surface(
        master,
        key,
        lambda: _build_topic_surface(master, instance),
    )
    metadata.update({
        "projection_base": "topic",
        "semantic_surface_cache_hit": hit,
    })
    return projected, metadata, depths, hit


def build_session_scene(masters: dict[str, dict[str, Any]], raw_instances: list[dict[str, Any]]) -> dict[str, Any]:
    if not raw_instances:
        raise ValueError("At least one Topic projection instance is required")

    instances = [normalize_projection_instance(spec, index, masters) for index, spec in enumerate(raw_instances)]
    ids = [item["id"] for item in instances]
    if len(ids) != len(set(ids)):
        raise ValueError("Projection instance ids must be unique")

    by_master: dict[str, list[dict[str, Any]]] = {}
    for instance in instances:
        master = masters[instance["master_ref"]]
        semantic_graph, metadata, hierarchy_depths, semantic_hit = _semantic_surface(master, instance)
        semantic_key = _semantic_cache_key(instance)
        visual_key = (*semantic_key, instance["projection_generator"])
        visual_projection, visual_hit = cached_visual_surface(
            master,
            visual_key,
            lambda: build_topic_visual(semantic_graph, instance["projection_generator"]),
        )
        visual_projection = apply_scope_style(visual_projection, instance["scope_style"])
        metadata.update({
            "scope_style": instance["scope_style"],
            "visual_surface_cache_hit": visual_hit,
            "server_semantic_materialization": not semantic_hit,
            "server_visual_materialization": not visual_hit,
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
        scene = compose_projection_instances(
            items,
            master["tree"],
            include_cross_projection_connections=True,
        )
        for obj in scene.get("objects", []):
            obj["master_ref"] = master_ref
        scenes.append((master_ref, scene))

    base_master_ref, base_scene = scenes[0]
    merged = deepcopy(base_scene)
    merged["objects"] = []
    merged["connections"] = []
    merged["connection_channels"] = {}
    for master_ref, scene in scenes:
        merged["objects"].extend(deepcopy(scene.get("objects", [])))
        merged["connections"].extend(deepcopy(scene.get("connections", [])))
        for key, value in scene.get("connection_channels", {}).items():
            merged["connection_channels"].setdefault(key, deepcopy(value))

    merged["composition"] = {
        "master_count": len(masters),
        "projection_count": len(instances),
        "master_refs": list(masters),
        "projection_types": ["topic"],
        "projection_master_rule": "each Topic projection references one master; masters may feed many Topic projections",
        "structure_tree_indexes": "resolved_once_at_import",
        "projection_surfaces": "cached_after_first_materialization",
        "projection_contract": "topic + scope + atlas + scope_style + projection_dimension",
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
