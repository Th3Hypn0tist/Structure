from __future__ import annotations

from copy import deepcopy
from typing import Any

FORMAT = "STRUCTUREPROJECTOR_SCENE"
VERSION = "1.0"

DEFAULT_CHANNEL_STYLES = {
    "structural": {"enabled": True, "color": "#AAB2C2"},
    "semantic": {"enabled": True, "color": "#087CFF"},
    "relations": {"enabled": True, "color": "#087CFF"},
    "dependencies": {"enabled": True, "color": "#FFD83D"},
    "ownership": {"enabled": False, "color": "#FF176B"},
    "authority": {"enabled": False, "color": "#FF3B30"},
    "binding": {"enabled": False, "color": "#B46CFF"},
    "tree": {"enabled": True, "color": "#AAB2C2"},
}


def new_scene(*, projection_id: str, source_tree: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": FORMAT,
        "version": VERSION,
        "projection_id": projection_id,
        "source_tree": {
            "format": source_tree.get("format"),
            "version": source_tree.get("version"),
            "input_module": source_tree.get("input_module"),
            "source": deepcopy(source_tree.get("source", {})),
        },
        "variables": {},
        "objects": [],
        "connections": [],
        "connection_channels": deepcopy(DEFAULT_CHANNEL_STYLES),
        "groups": [],
        "bounds": None,
        "camera_hint": None,
    }


def projection_to_scene(
    projection: dict[str, Any],
    source_tree: dict[str, Any],
    *,
    primitive: str = "box",
    connection_primitive: str = "line",
) -> dict[str, Any]:
    """Translate projection layout into the Scene Contract.

    The projection owns spatial placement. SceneObject owns one or more Nodes.
    Node owns primitive/geometry/style. Connections remain independent semantic
    records and may be enabled concurrently by channel.
    """
    scene = new_scene(projection_id=str(projection.get("id") or "projection"), source_tree=source_tree)
    entry_index = {str(e.get("id")): e for e in source_tree.get("entries", [])}
    link_index = {str(l.get("id")): l for l in source_tree.get("links", []) if l.get("id") is not None}

    for projected in projection.get("nodes", []):
        entry_id = str(projected.get("id"))
        entry = entry_index.get(entry_id, {})
        scene["objects"].append({
            "id": f"object:{entry_id}",
            "source_ref": entry_id,
            "variables": {},
            "transform": {
                "position": {
                    "x": float(projected.get("x", 0) or 0),
                    "y": float(projected.get("y", 0) or 0),
                    "z": float(projected.get("z", 0) or 0),
                },
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
            },
            "nodes": [{
                "id": "body",
                "primitive": primitive,
                "geometry": {
                    "width": projected.get("width"),
                    "height": projected.get("height"),
                    "depth": projected.get("depth"),
                    "radius": projected.get("radius"),
                },
                "transform": {
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
                },
                "style": {},
                "properties": {
                    "name": entry.get("name", projected.get("name")),
                    "type": entry.get("type", projected.get("type")),
                    "status": entry.get("status", projected.get("status")),
                },
                "anchors": {
                    "center": {"x": 0.0, "y": 0.0, "z": 0.0},
                },
                "bindings": [],
            }],
        })

    for edge in projection.get("edges", []):
        source_id = str(edge.get("source"))
        target_id = str(edge.get("target"))
        raw_link = link_index.get(str(edge.get("id")), {})
        channel = str(edge.get("dimension") or raw_link.get("dimension") or "semantic")
        if channel not in scene["connection_channels"]:
            scene["connection_channels"][channel] = {"enabled": True, "color": "#AAB2C2"}
        scene["connections"].append({
            "id": edge.get("id") or f"connection:{channel}:{source_id}->{target_id}",
            "channel": channel,
            "type": edge.get("type") or raw_link.get("type") or channel,
            "source_ref": raw_link.get("id") or edge.get("id"),
            "from": {"object": f"object:{source_id}", "node": "body", "anchor": "center"},
            "to": {"object": f"object:{target_id}", "node": "body", "anchor": "center"},
            "primitive": connection_primitive,
            "style_ref": channel,
            "style": {},
        })

    scene["groups"] = deepcopy(projection.get("groups", []))
    scene["bounds"] = deepcopy(projection.get("bounds3d") or projection.get("bounds"))
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
            if not node.get("primitive"):
                errors.append({"id": "SP_SCENE_NODE_PRIMITIVE", "message": f"Node {oid}/{nid} requires primitive"})

    for connection in scene.get("connections", []):
        for endpoint_name in ("from", "to"):
            endpoint = connection.get(endpoint_name) or {}
            oid = endpoint.get("object")
            nid = endpoint.get("node")
            if oid not in object_ids:
                errors.append({"id": "SP_SCENE_CONNECTION_OBJECT", "message": f"Unresolved {endpoint_name} object: {oid}"})
            elif nid not in node_ids.get(oid, set()):
                errors.append({"id": "SP_SCENE_CONNECTION_NODE", "message": f"Unresolved {endpoint_name} node: {oid}/{nid}"})
    return errors
