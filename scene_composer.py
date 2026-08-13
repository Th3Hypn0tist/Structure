from __future__ import annotations

from copy import deepcopy
from typing import Any

from primitive_registry import resolve_primitive
from scene_contract import new_scene, projection_connections, projection_to_object, validate_scene


def _default_offset(index: int, spacing: float = 1800.0) -> dict[str, Any]:
    return {
        "position": {"x": index * spacing, "y": 0.0, "z": 0.0},
        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
    }


def _recenter_projection(projection: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(projection)
    nodes = out.get("nodes", [])
    if not nodes:
        out["local_origin"] = {"x": 0.0, "y": 0.0, "z": 0.0}
        return out

    xs = [float(node.get("x", 0) or 0) for node in nodes]
    ys = [float(node.get("y", 0) or 0) for node in nodes]
    zs = [float(node.get("z", 0) or 0) for node in nodes]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    cz = (min(zs) + max(zs)) / 2.0
    for node in nodes:
        node["x"] = float(node.get("x", 0) or 0) - cx
        node["y"] = float(node.get("y", 0) or 0) - cy
        node["z"] = float(node.get("z", 0) or 0) - cz
    out["local_origin"] = {"x": cx, "y": cy, "z": cz}
    return out


def _append_cross_projection_connections(
    scene: dict[str, Any],
    source_tree: dict[str, Any],
    nodes_by_object: dict[str, set[str]],
    *,
    connection_primitive_ref: str,
) -> None:
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
                    "primitive_ref": connection_primitive_ref,
                    "style_ref": channel,
                    "style": {},
                    "provenance": deepcopy(link.get("provenance", {})),
                })


def _finish_scene(scene: dict[str, Any]) -> dict[str, Any]:
    for connection in scene["connections"]:
        channel = str(connection.get("channel") or "semantic")
        scene["connection_channels"].setdefault(channel, {"enabled": True, "color": "#AAB2C2"})

    scene["composition"] = {
        "projection_count": len(scene["objects"]),
        "node_instance_count": sum(len(obj.get("nodes", [])) for obj in scene["objects"]),
        "primitive_instances": True,
        "internal_connections": sum(1 for c in scene["connections"] if c.get("scope") == "projection"),
        "cross_projection_connections": sum(1 for c in scene["connections"] if c.get("scope") == "cross_projection"),
        "rule": "cross-projection connections originate only from explicit StructureTree links",
    }
    scene["validation_errors"] = validate_scene(scene)
    return scene


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
    transforms = transforms or {}
    scene = new_scene(source_tree=source_tree)
    nodes_by_object: dict[str, set[str]] = {}
    connection_primitive_ref, _definition = resolve_primitive(connection_primitive, connection=True)

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
        nodes_by_object[object_id] = {str(node.get("id")) for node in obj.get("nodes", [])}
        if include_internal_connections:
            scene["connections"].extend(projection_connections(
                projection,
                source_tree,
                object_id=object_id,
                connection_primitive=connection_primitive_ref,
            ))

    if include_cross_projection_connections:
        _append_cross_projection_connections(
            scene,
            source_tree,
            nodes_by_object,
            connection_primitive_ref=connection_primitive_ref,
        )
    return _finish_scene(scene)


def compose_projection_instances(
    items: list[dict[str, Any]],
    source_tree: dict[str, Any],
    *,
    primitive: str = "box",
    connection_primitive: str = "line",
    include_internal_connections: bool = True,
    include_cross_projection_connections: bool = True,
) -> dict[str, Any]:
    """Compose named projection instances with independent style/root identity."""
    scene = new_scene(source_tree=source_tree)
    nodes_by_object: dict[str, set[str]] = {}
    connection_primitive_ref, _definition = resolve_primitive(connection_primitive, connection=True)

    for index, item in enumerate(items):
        instance = item["instance"]
        projection = _recenter_projection(item["projection"])
        hierarchy_depths = item.get("hierarchy_depths", {})
        filter_metadata = deepcopy(item.get("filter_metadata", {}))
        instance_id = str(instance["id"])
        object_id = f"projection-instance:{instance_id}"
        transform = deepcopy(instance.get("transform") or _default_offset(index))

        obj = projection_to_object(
            projection,
            source_tree,
            object_id=object_id,
            transform=transform,
            primitive=primitive,
        )
        obj["name"] = instance["name"]
        obj["title"] = instance["name"]
        obj["instance_id"] = instance_id
        obj["projection_style"] = instance["projection_style"]
        obj["projection_dimension"] = instance["projection_dimension"]
        obj["projection_generator"] = instance["projection_generator"]
        obj["root_topic"] = instance["root_topic"]
        obj["dependency_depth"] = instance["dependency_depth"]
        obj["relation_depth"] = instance["dependency_depth"]
        obj["filter"] = filter_metadata
        obj["local_origin"] = deepcopy(projection.get("local_origin", {}))
        obj["style_defaults"] = {
            "even": "#087CFF",
            "odd": "#AAB2C2",
            "title": "#0B356B",
            "label_text": "#FFFFFF",
            "root_label_text": "#FFFFFF",
        }

        for node in obj.get("nodes", []):
            node_id = str(node.get("source_ref") or node.get("id"))
            node.setdefault("properties", {})["hierarchy_depth"] = hierarchy_depths.get(node_id)

        scene["objects"].append(obj)
        nodes_by_object[object_id] = {str(node.get("id")) for node in obj.get("nodes", [])}

        if include_internal_connections:
            scene["connections"].extend(projection_connections(
                projection,
                source_tree,
                object_id=object_id,
                connection_primitive=connection_primitive_ref,
            ))

    if include_cross_projection_connections:
        _append_cross_projection_connections(
            scene,
            source_tree,
            nodes_by_object,
            connection_primitive_ref=connection_primitive_ref,
        )
    return _finish_scene(scene)
