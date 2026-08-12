from __future__ import annotations

from copy import deepcopy
from typing import Any

from primitive_registry import resolve_primitive

FORMAT = "STRUCTUREPROJECTOR_SCENE"
VERSION = "1.1"

DEFAULT_CHANNEL_STYLES = {
    "structural": {"enabled": True, "color": "#AAB2C2"},
    "containment": {"enabled": True, "color": "#AAB2C2"},
    "semantic": {"enabled": True, "color": "#087CFF"},
    "relations": {"enabled": True, "color": "#087CFF"},
    "dependencies": {"enabled": True, "color": "#FFD83D"},
    "ownership": {"enabled": False, "color": "#FF176B"},
    "authority": {"enabled": False, "color": "#FF3B30"},
    "binding": {"enabled": False, "color": "#B46CFF"},
    "tree": {"enabled": True, "color": "#AAB2C2"},
}


def _zero_transform() -> dict[str, Any]:
    return {
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
    }


def new_scene(*, source_tree: dict[str, Any] | None = None) -> dict[str, Any]:
    tree = source_tree or {}
    return {
        "format": FORMAT,
        "version": VERSION,
        "source_tree": {
            "format": tree.get("format"),
            "version": tree.get("version"),
            "input_module": tree.get("input_module"),
            "source": deepcopy(tree.get("source", {})),
        },
        "variables": {},
        "objects": [],
        "connections": [],
        "connection_channels": deepcopy(DEFAULT_CHANNEL_STYLES),
        "bounds": None,
        "camera_hint": None,
    }


def _node_geometry_parameters(projected: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for key in ("width", "height", "depth", "radius"):
        value = projected.get(key)
        if value is not None:
            params[key] = value
    return params


def projection_to_object(
    projection: dict[str, Any],
    source_tree: dict[str, Any],
    *,
    object_id: str | None = None,
    transform: dict[str, Any] | None = None,
    primitive: str = "box",
) -> dict[str, Any]:
    """Convert one projection into one composable SceneObject.

    SceneObject is the projection instance. Nodes are lightweight primitive
    instances: they reference shared primitive geometry and carry only local
    transform, geometry parameters, style and source properties.
    """
    projection_id = str(projection.get("id") or "projection")
    entry_index = {str(e.get("id")): e for e in source_tree.get("entries", [])}
    primitive_ref, _definition = resolve_primitive(primitive)
    nodes: list[dict[str, Any]] = []

    for projected in projection.get("nodes", []):
        entry_id = str(projected.get("id"))
        if not entry_id:
            continue
        entry = entry_index.get(entry_id, {})
        nodes.append({
            "id": entry_id,
            "source_ref": entry_id,
            "primitive_ref": primitive_ref,
            "transform": {
                "position": {
                    "x": float(projected.get("x", 0) or 0),
                    "y": float(projected.get("y", 0) or 0),
                    "z": float(projected.get("z", 0) or 0),
                },
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
            },
            "geometry_parameters": _node_geometry_parameters(projected),
            "style": {},
            "properties": {
                "name": entry.get("name", projected.get("name")),
                "type": entry.get("type", projected.get("type")),
                "status": entry.get("status", projected.get("status")),
                "kind": entry.get("kind", projected.get("kind")),
            },
            "bindings": [],
        })

    return {
        "id": object_id or f"projection:{projection_id}",
        "kind": "projection",
        "projection_id": projection_id,
        "title": projection.get("title") or projection_id,
        "source_ref": {
            "input_module": source_tree.get("input_module"),
            "revision": source_tree.get("source", {}).get("revision"),
        },
        "variables": {},
        "transform": deepcopy(transform or _zero_transform()),
        "nodes": nodes,
        "groups": deepcopy(projection.get("groups", [])),
        "bounds": deepcopy(projection.get("bounds3d") or projection.get("bounds")),
        "extent": projection.get("extent"),
    }


def projection_connections(
    projection: dict[str, Any],
    source_tree: dict[str, Any],
    *,
    object_id: str,
    connection_primitive: str = "line",
) -> list[dict[str, Any]]:
    link_index = {str(l.get("id")): l for l in source_tree.get("links", []) if l.get("id") is not None}
    node_ids = {str(n.get("id")) for n in projection.get("nodes", [])}
    primitive_ref, _definition = resolve_primitive(connection_primitive, connection=True)
    connections: list[dict[str, Any]] = []

    for edge in projection.get("edges", []):
        source_id = str(edge.get("source"))
        target_id = str(edge.get("target"))
        if source_id not in node_ids or target_id not in node_ids:
            continue
        raw_link = link_index.get(str(edge.get("id")), {})
        channel = str(edge.get("dimension") or raw_link.get("dimension") or "semantic")
        connections.append({
            "id": f"{object_id}:{edge.get('id') or f'{channel}:{source_id}->{target_id}'}",
            "scope": "projection",
            "channel": channel,
            "type": edge.get("type") or raw_link.get("type") or channel,
            "source_ref": raw_link.get("id") or edge.get("id"),
            "from": {"object": object_id, "node": source_id, "anchor": "center"},
            "to": {"object": object_id, "node": target_id, "anchor": "center"},
            "primitive_ref": primitive_ref,
            "style_ref": channel,
            "style": {},
        })
    return connections


def projection_to_scene(
    projection: dict[str, Any],
    source_tree: dict[str, Any],
    *,
    primitive: str = "box",
    connection_primitive: str = "line",
) -> dict[str, Any]:
    scene = new_scene(source_tree=source_tree)
    obj = projection_to_object(projection, source_tree, primitive=primitive)
    scene["objects"].append(obj)
    scene["connections"].extend(projection_connections(
        projection,
        source_tree,
        object_id=obj["id"],
        connection_primitive=connection_primitive,
    ))
    for connection in scene["connections"]:
        channel = connection["channel"]
        scene["connection_channels"].setdefault(channel, {"enabled": True, "color": "#AAB2C2"})
    scene["bounds"] = deepcopy(obj.get("bounds"))
    scene["camera_hint"] = deepcopy(projection.get("camera_hint"))
    return scene


def validate_scene(scene: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if scene.get("format") != FORMAT:
        errors.append({"id": "SP_SCENE_FORMAT", "message": f"Expected {FORMAT}"})
    if scene.get("version") != VERSION:
        errors.append({"id": "SP_SCENE_VERSION", "message": f"Expected Scene version {VERSION}"})

    object_ids: set[str] = set()
    node_ids: dict[str, set[str]] = {}
    for obj in scene.get("objects", []):
        oid = obj.get("id")
        if not isinstance(oid, str) or not oid:
            errors.append({"id": "SP_SCENE_OBJECT_ID", "message": "SceneObject requires id"})
            continue
        if oid in object_ids:
            errors.append({"id": "SP_SCENE_DUPLICATE_OBJECT", "message": f"Duplicate SceneObject: {oid}"})
        object_ids.add(oid)
        node_ids[oid] = set()
        for node in obj.get("nodes", []):
            nid = node.get("id")
            if not isinstance(nid, str) or not nid:
                errors.append({"id": "SP_SCENE_NODE_ID", "message": f"Node in {oid} requires id"})
                continue
            if nid in node_ids[oid]:
                errors.append({"id": "SP_SCENE_DUPLICATE_NODE", "message": f"Duplicate Node {oid}/{nid}"})
            node_ids[oid].add(nid)
            primitive_ref = node.get("primitive_ref")
            try:
                resolve_primitive(primitive_ref)
            except Exception:
                errors.append({"id": "SP_SCENE_NODE_PRIMITIVE", "message": f"Unresolved primitive_ref for Node {oid}/{nid}: {primitive_ref}"})
            if "geometry" in node or "primitive" in node:
                errors.append({"id": "SP_SCENE_NODE_INSTANCE_ONLY", "message": f"Node {oid}/{nid} must not embed primitive geometry"})

    connection_ids: set[str] = set()
    for connection in scene.get("connections", []):
        cid = connection.get("id")
        if isinstance(cid, str):
            if cid in connection_ids:
                errors.append({"id": "SP_SCENE_DUPLICATE_CONNECTION", "message": f"Duplicate SceneConnection: {cid}"})
            connection_ids.add(cid)
        channel = connection.get("channel")
        if not isinstance(channel, str) or not channel:
            errors.append({"id": "SP_SCENE_CONNECTION_CHANNEL", "message": "SceneConnection requires channel"})
        try:
            resolve_primitive(connection.get("primitive_ref"), connection=True)
        except Exception:
            errors.append({"id": "SP_SCENE_CONNECTION_PRIMITIVE", "message": f"Unresolved connection primitive_ref: {connection.get('primitive_ref')}"})
        for endpoint_name in ("from", "to"):
            endpoint = connection.get(endpoint_name) or {}
            oid = endpoint.get("object")
            nid = endpoint.get("node")
            if oid not in object_ids:
                errors.append({"id": "SP_SCENE_CONNECTION_OBJECT", "message": f"Unresolved {endpoint_name} object: {oid}"})
            elif nid not in node_ids.get(oid, set()):
                errors.append({"id": "SP_SCENE_CONNECTION_NODE", "message": f"Unresolved {endpoint_name} node: {oid}/{nid}"})
    return errors
