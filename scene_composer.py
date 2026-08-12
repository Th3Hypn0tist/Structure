from __future__ import annotations

from copy import deepcopy
from typing import Any

from scene_contract import new_scene, projection_connections, projection_to_object, validate_scene


def _default_offset(index: int, spacing: float = 1800.0) -> dict[str, Any]:
    return {
        "position": {"x": index * spacing, "y": 0.0, "z": 0.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
    }


def compose_scene(
    projections: list[dict[str, Any]],
    source_tree: dict[str, Any],
    *,
    transforms: dict[str, dict[str, Any]] | None = None,
    primitive: str = "box",
    connection_primitive: str = "line",
    include_internal_connections: bool = True,
    include_cross_projection_connections: bool = True,
) -> dict[str, Any]:
    """Compose multiple projections into one Scene.

    Each projection is one SceneObject. Connections between different
    SceneObjects are generated only from explicit StructureTree links whose
    source and target entries are present in the corresponding projection
    objects. No relationship is inferred from layout, names or proximity.
    """
    transforms = transforms or {}
    scene = new_scene(source_tree=source_tree)
    projection_by_object: dict[str, dict[str, Any]] = {}
    nodes_by_object: dict[str, set[str]] = {}

    for index, projection in enumerate(projections):
        projection_id = str(projection.get("id") or f"projection-{index}")
        object_id = f"projection:{projection_id}"
        transform = transforms.get(object_id) or transforms.get(projection_id) or _default_offset(index)
        obj = projection_to_object(
            projection,
            source_tree,
            object_id=object_id,
            transform=transform,
            primitive=primitive,
        )
        scene["objects"].append(obj)
        projection_by_object[object_id] = projection
        nodes_by_object[object_id] = {str(node.get("id")) for node in obj.get("nodes", [])}

        if include_internal_connections:
            scene["connections"].extend(projection_connections(
                projection,
                source_tree,
                object_id=object_id,
                connection_primitive=connection_primitive,
            ))

    if include_cross_projection_connections:
        for link_index, link in enumerate(source_tree.get("links", [])):
            source_id = str(link.get("source_id") or "")
            target_id = str(link.get("target_id") or "")
            if not source_id or not target_id:
                continue
            channel = str(link.get("dimension") or "semantic")
            link_id = str(link.get("id") or f"link-{link_index}")
            source_objects = [oid for oid, ids in nodes_by_object.items() if source_id in ids]
            target_objects = [oid for oid, ids in nodes_by_object.items() if target_id in ids]
            for source_object in source_objects:
                for target_object in target_objects:
                    if source_object == target_object:
                        continue
                    scene["connections"].append({
                        "id": f"cross:{link_id}:{source_object}->{target_object}",
                        "scope": "cross_projection",
                        "channel": channel,
                        "type": link.get("type") or channel,
                        "source_ref": link.get("id"),
                        "from": {"object": source_object, "node": source_id, "anchor": "center"},
                        "to": {"object": target_object, "node": target_id, "anchor": "center"},
                        "primitive": connection_primitive,
                        "style_ref": channel,
                        "style": {},
                        "provenance": deepcopy(link.get("provenance", {})),
                    })

    for connection in scene["connections"]:
        channel = str(connection.get("channel") or "semantic")
        scene["connection_channels"].setdefault(channel, {"enabled": True, "color": "#AAB2C2"})

    scene["composition"] = {
        "projection_count": len(scene["objects"]),
        "internal_connections": sum(1 for c in scene["connections"] if c.get("scope") == "projection"),
        "cross_projection_connections": sum(1 for c in scene["connections"] if c.get("scope") == "cross_projection"),
        "rule": "cross-projection connections originate only from explicit StructureTree links",
    }
    scene["validation_errors"] = validate_scene(scene)
    return scene
