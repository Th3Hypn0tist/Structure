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


def compose_multi_input_instances(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Compose independent projection instances from independent read-only inputs.

    No cross-input connections are manufactured. Cross-input relationships belong
    to explicit Mapper/mapping evidence and can be added later as their own channel.
    """
    scene = new_scene(source_tree={})
    connection_primitive_ref, _definition = resolve_primitive("line", connection=True)

    for index, item in enumerate(items):
        instance = item["instance"]
        input_spec = item["input"]
        tree = item["tree"]
        projection = _recenter_projection(item["projection"])
        hierarchy_depths = item.get("hierarchy_depths", {})
        filter_metadata = deepcopy(item.get("filter_metadata", {}))
        instance_id = str(instance["id"])
        object_id = f"projection-instance:{instance_id}"
        transform = deepcopy(instance.get("transform") or _default_offset(index))

        obj = projection_to_object(
            projection,
            tree,
            object_id=object_id,
            transform=transform,
            primitive="box",
        )
        obj["name"] = instance["name"]
        obj["title"] = instance["name"]
        obj["instance_id"] = instance_id
        obj["input_id"] = input_spec["id"]
        obj["input_name"] = input_spec["name"]
        obj["input_role"] = input_spec["role"]
        obj["input_detector"] = input_spec["detector"]
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
            props = node.setdefault("properties", {})
            props["hierarchy_depth"] = hierarchy_depths.get(node_id)
            props["input_id"] = input_spec["id"]
            props["input_name"] = input_spec["name"]
            props["input_role"] = input_spec["role"]

        scene["objects"].append(obj)
        scene["connections"].extend(projection_connections(
            projection,
            tree,
            object_id=object_id,
            connection_primitive=connection_primitive_ref,
        ))

    for connection in scene["connections"]:
        channel = str(connection.get("channel") or "semantic")
        scene["connection_channels"].setdefault(channel, {"enabled": True, "color": "#AAB2C2"})

    groups: dict[str, dict[str, Any]] = {}
    for obj in scene["objects"]:
        input_id = str(obj.get("input_id") or "unknown")
        group = groups.setdefault(input_id, {
            "input_id": input_id,
            "input_name": obj.get("input_name"),
            "input_role": obj.get("input_role"),
            "object_ids": [],
        })
        group["object_ids"].append(obj["id"])

    scene["input_groups"] = sorted(groups.values(), key=lambda item: (str(item.get("input_role") or ""), str(item.get("input_name") or "")))
    scene["composition"] = {
        "projection_count": len(scene["objects"]),
        "input_count": len(groups),
        "node_instance_count": sum(len(obj.get("nodes", [])) for obj in scene["objects"]),
        "primitive_instances": True,
        "internal_connections": len(scene["connections"]),
        "cross_input_connections": 0,
        "rule": "each projection instance reads exactly one input; cross-input relations require explicit mapping evidence",
    }
    scene["validation_errors"] = validate_scene(scene)
    return scene
