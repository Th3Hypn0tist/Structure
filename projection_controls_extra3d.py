from __future__ import annotations

from copy import deepcopy
from typing import Any


EXTRA_IDS = {
    "atlas_3d",
    "relation_web_3d",
    "adjacency_matrix_3d",
    "lifecycle_lanes_3d",
    "dependency_flow_3d",
}


def _slider(control_id: str, label: str, minimum: float, maximum: float, step: float, default: float) -> dict[str, Any]:
    return {
        "id": control_id,
        "label": label,
        "type": "range",
        "min": minimum,
        "max": maximum,
        "step": step,
        "default": default,
    }


CONTROLS = [
    _slider("scale_x", "X spread", 0.35, 2.80, 0.05, 1.0),
    _slider("scale_y", "Y spread", 0.35, 2.80, 0.05, 1.0),
    _slider("scale_z", "Z spread", 0.35, 2.80, 0.05, 1.0),
    _slider("node_scale", "Node size", 0.55, 1.80, 0.05, 1.0),
    _slider("label_scale", "Label size", 0.65, 1.60, 0.05, 1.0),
    _slider("edge_opacity", "Edge opacity", 0.00, 1.00, 0.05, 0.24),
    _slider("perspective", "Perspective", 500, 2200, 50, 1100),
    _slider("glow", "Glow", 0.00, 1.50, 0.05, 0.65),
    _slider("extrusion", "Extrusion", 0, 64, 2, 28),
    _slider("edge_glow", "Edge glow", 0.00, 1.50, 0.05, 0.45),
]

PRESETS = {
    "Neon Showcase": {"glow": 1.05, "extrusion": 38, "edge_glow": 0.80, "edge_opacity": 0.30, "perspective": 1050},
    "Subtle Spatial": {"glow": 0.30, "extrusion": 20, "edge_glow": 0.18, "edge_opacity": 0.18, "perspective": 1250},
    "Wide": {"scale_x": 1.45, "scale_y": 1.0, "scale_z": 1.45, "edge_opacity": 0.22},
    "Compact": {"scale_x": 0.75, "scale_y": 0.75, "scale_z": 0.75, "node_scale": 0.86, "label_scale": 0.90},
}


def supports(projection_id: str) -> bool:
    return projection_id in EXTRA_IDS


def schema_for(projection_id: str) -> dict[str, Any]:
    if projection_id not in EXTRA_IDS:
        return {"version": 1, "controls": [], "presets": {}}
    return {"version": 1, "controls": deepcopy(CONTROLS), "presets": deepcopy(PRESETS)}


def defaults_for(projection_id: str) -> dict[str, float]:
    if projection_id not in EXTRA_IDS:
        return {}
    return {c["id"]: c["default"] for c in CONTROLS}


def normalize_values(projection_id: str, supplied: dict[str, Any] | None) -> dict[str, float]:
    values = defaults_for(projection_id)
    supplied = supplied or {}
    if projection_id not in EXTRA_IDS:
        return values
    for control in CONTROLS:
        cid = control["id"]
        if cid not in supplied:
            continue
        try:
            value = float(supplied[cid])
        except (TypeError, ValueError):
            continue
        value = max(float(control["min"]), min(float(control["max"]), value))
        step = float(control["step"])
        if step > 0:
            base = float(control["min"])
            value = base + round((value - base) / step) * step
        values[cid] = value
    return values


def apply_controls(projection: dict[str, Any], supplied: dict[str, Any] | None = None) -> dict[str, Any]:
    result = deepcopy(projection)
    projection_id = str(result.get("id", ""))
    schema = schema_for(projection_id)
    values = normalize_values(projection_id, supplied)
    result["control_schema"] = schema["controls"]
    result["control_schema_version"] = schema["version"]
    result["control_values"] = values
    result["builtin_presets"] = schema["presets"]
    result.setdefault("style", {})

    sx, sy, sz = values.get("scale_x", 1.0), values.get("scale_y", 1.0), values.get("scale_z", 1.0)
    for node in result.get("nodes", []):
        node["x"] = float(node.get("x", 0.0)) * sx
        node["y"] = float(node.get("y", 0.0)) * sy
        node["z"] = float(node.get("z", 0.0)) * sz
    for group in result.get("groups", []):
        if "x" in group:
            group["x"] = float(group["x"]) * sx
        if "y" in group:
            group["y"] = float(group["y"]) * sy
        if "z" in group:
            group["z"] = float(group["z"]) * sz
        if "radius" in group:
            group["radius"] = float(group["radius"]) * max(sx, sz)

    result["extent"] = float(result.get("extent", 900.0)) * max(sx, sy, sz)
    result["style"].update({
        "node_scale": values.get("node_scale", 1.0),
        "label_scale": values.get("label_scale", 1.0),
        "edge_opacity": values.get("edge_opacity", 0.24),
        "perspective": values.get("perspective", 1100),
        "glow": values.get("glow", 0.65),
        "extrusion": values.get("extrusion", 28),
        "edge_glow": values.get("edge_glow", 0.45),
    })
    return result
