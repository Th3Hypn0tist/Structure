from __future__ import annotations

from copy import deepcopy
from typing import Any


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


COMMON_2D = [
    _slider("spacing_x", "Horizontal spacing", 0.45, 2.50, 0.05, 1.0),
    _slider("spacing_y", "Vertical spacing", 0.45, 2.50, 0.05, 1.0),
    _slider("node_scale", "Node size", 0.55, 1.80, 0.05, 1.0),
    _slider("label_scale", "Label size", 0.65, 1.60, 0.05, 1.0),
    _slider("edge_opacity", "Edge opacity", 0.00, 1.00, 0.05, 0.40),
]

COMMON_3D = [
    _slider("scale_x", "X spread", 0.35, 2.80, 0.05, 1.0),
    _slider("scale_y", "Y spread", 0.35, 2.80, 0.05, 1.0),
    _slider("scale_z", "Z spread", 0.35, 2.80, 0.05, 1.0),
    _slider("node_scale", "Node size", 0.55, 1.80, 0.05, 1.0),
    _slider("label_scale", "Label size", 0.65, 1.60, 0.05, 1.0),
    _slider("edge_opacity", "Edge opacity", 0.00, 1.00, 0.05, 0.22),
    _slider("perspective", "Perspective", 500, 2200, 50, 1100),
    _slider("glow", "Glow", 0.00, 1.50, 0.05, 0.65),
    _slider("extrusion", "Extrusion", 0, 64, 2, 28),
    _slider("edge_glow", "Edge glow", 0.00, 1.50, 0.05, 0.45),
]


SCHEMAS: dict[str, dict[str, Any]] = {
    "atlas_2d": {
        "version": 1,
        "controls": COMMON_2D,
        "presets": {
            "Dense": {"spacing_x": 0.72, "spacing_y": 0.72, "node_scale": 0.86, "label_scale": 0.90, "edge_opacity": 0.22},
            "Presentation": {"spacing_x": 1.18, "spacing_y": 1.15, "node_scale": 1.12, "label_scale": 1.12, "edge_opacity": 0.28},
        },
    },
    "relation_web_2d": {
        "version": 1,
        "controls": COMMON_2D,
        "presets": {
            "Compact Web": {"spacing_x": 0.72, "spacing_y": 0.72, "node_scale": 0.82, "label_scale": 0.86, "edge_opacity": 0.20},
            "Readable Web": {"spacing_x": 1.42, "spacing_y": 1.42, "node_scale": 1.05, "label_scale": 1.05, "edge_opacity": 0.32},
        },
    },
    "adjacency_matrix_2d": {
        "version": 1,
        "controls": [
            _slider("cell_size", "Cell size", 8, 42, 1, 18),
            _slider("label_size", "Label margin", 120, 520, 10, 260),
            _slider("label_scale", "Label size", 0.65, 1.70, 0.05, 1.0),
            _slider("cell_opacity", "Cell opacity", 0.15, 1.00, 0.05, 0.72),
        ],
        "presets": {
            "Dense Matrix": {"cell_size": 11, "label_size": 210, "label_scale": 0.82, "cell_opacity": 0.72},
            "Inspection": {"cell_size": 26, "label_size": 340, "label_scale": 1.14, "cell_opacity": 0.82},
        },
    },
    "lifecycle_lanes_2d": {
        "version": 1,
        "controls": COMMON_2D,
        "presets": {
            "Dashboard": {"spacing_x": 0.92, "spacing_y": 0.70, "node_scale": 0.90, "label_scale": 0.92, "edge_opacity": 0.12},
            "Review": {"spacing_x": 1.22, "spacing_y": 1.18, "node_scale": 1.10, "label_scale": 1.10, "edge_opacity": 0.10},
        },
    },
    "dependency_flow_2d": {
        "version": 1,
        "controls": COMMON_2D,
        "presets": {
            "Compact Flow": {"spacing_x": 0.82, "spacing_y": 0.68, "node_scale": 0.88, "label_scale": 0.90, "edge_opacity": 0.32},
            "Trace Flow": {"spacing_x": 1.18, "spacing_y": 1.48, "node_scale": 1.02, "label_scale": 1.04, "edge_opacity": 0.62},
        },
    },
    "semantic_galaxy_3d": {
        "version": 1,
        "controls": COMMON_3D,
        "presets": {
            "Compact Galaxy": {"scale_x": 0.70, "scale_y": 0.70, "scale_z": 0.70, "node_scale": 0.82, "label_scale": 0.86, "edge_opacity": 0.10, "perspective": 950},
            "Exploded Galaxy": {"scale_x": 1.55, "scale_y": 1.55, "scale_z": 1.55, "node_scale": 1.00, "label_scale": 1.00, "edge_opacity": 0.18, "perspective": 1250},
        },
    },
    "role_layers_3d": {
        "version": 1,
        "controls": COMMON_3D,
        "presets": {
            "Tight Layers": {"scale_x": 0.90, "scale_y": 0.65, "scale_z": 0.90, "node_scale": 0.88, "label_scale": 0.90, "edge_opacity": 0.12, "perspective": 1000},
            "Separated Layers": {"scale_x": 1.10, "scale_y": 1.65, "scale_z": 1.10, "node_scale": 1.00, "label_scale": 1.00, "edge_opacity": 0.20, "perspective": 1250},
        },
    },
    "dependency_tower_3d": {
        "version": 1,
        "controls": COMMON_3D,
        "presets": {
            "Compact Tower": {"scale_x": 0.78, "scale_y": 0.72, "scale_z": 0.78, "node_scale": 0.88, "label_scale": 0.90, "edge_opacity": 0.20, "perspective": 1000},
            "Tall Tower": {"scale_x": 1.05, "scale_y": 1.75, "scale_z": 1.05, "node_scale": 0.98, "label_scale": 1.00, "edge_opacity": 0.35, "perspective": 1300},
        },
    },
    "authority_space_3d": {
        "version": 1,
        "controls": COMMON_3D,
        "presets": {
            "Authority Focus": {"scale_x": 0.82, "scale_y": 0.90, "scale_z": 1.65, "node_scale": 0.95, "label_scale": 0.96, "edge_opacity": 0.35, "perspective": 1150},
            "Ownership Focus": {"scale_x": 1.65, "scale_y": 0.90, "scale_z": 0.82, "node_scale": 0.95, "label_scale": 0.96, "edge_opacity": 0.35, "perspective": 1150},
        },
    },
    "relation_orbits_3d": {
        "version": 1,
        "controls": COMMON_3D,
        "presets": {
            "Flat Orbits": {"scale_x": 1.15, "scale_y": 0.40, "scale_z": 1.15, "node_scale": 0.90, "label_scale": 0.90, "edge_opacity": 0.10, "perspective": 1050},
            "Deep Orbits": {"scale_x": 1.35, "scale_y": 1.15, "scale_z": 1.35, "node_scale": 0.98, "label_scale": 0.98, "edge_opacity": 0.20, "perspective": 1300},
        },
    },
}

# Additive FX presets apply to every 3D projection. Missing layout values fall
# back to the projection's declared defaults, so these do not change semantics.
for _projection_id, _schema in SCHEMAS.items():
    if not _projection_id.endswith("_3d"):
        continue
    _schema["presets"].setdefault(
        "Neon Showcase",
        {"glow": 1.05, "extrusion": 38, "edge_glow": 0.80, "edge_opacity": 0.30, "perspective": 1050},
    )
    _schema["presets"].setdefault(
        "Subtle Spatial",
        {"glow": 0.30, "extrusion": 20, "edge_glow": 0.18, "edge_opacity": 0.18, "perspective": 1250},
    )


def schema_for(projection_id: str) -> dict[str, Any]:
    schema = SCHEMAS.get(projection_id)
    if schema is None:
        return {"version": 1, "controls": [], "presets": {}}
    return deepcopy(schema)


def defaults_for(projection_id: str) -> dict[str, float]:
    schema = SCHEMAS.get(projection_id, {})
    return {
        control["id"]: control["default"]
        for control in schema.get("controls", [])
    }


def normalize_values(projection_id: str, supplied: dict[str, Any] | None) -> dict[str, float]:
    supplied = supplied or {}
    values = defaults_for(projection_id)
    for control in SCHEMAS.get(projection_id, {}).get("controls", []):
        control_id = control["id"]
        if control_id not in supplied:
            continue
        try:
            value = float(supplied[control_id])
        except (TypeError, ValueError):
            continue
        value = max(float(control["min"]), min(float(control["max"]), value))
        step = float(control["step"])
        if step > 0:
            base = float(control["min"])
            value = base + round((value - base) / step) * step
        values[control_id] = value
    return values


def _scale_rect(node: dict[str, Any], sx: float, sy: float, node_scale: float) -> None:
    if "x" in node:
        node["x"] = float(node["x"]) * sx
    if "y" in node:
        node["y"] = float(node["y"]) * sy
    if "width" in node:
        original = float(node["width"])
        delta = original * (node_scale - 1.0)
        node["x"] = float(node.get("x", 0.0)) - delta / 2.0
        node["width"] = original * node_scale
    if "height" in node:
        original = float(node["height"])
        delta = original * (node_scale - 1.0)
        node["y"] = float(node.get("y", 0.0)) - delta / 2.0
        node["height"] = original * node_scale
    if "radius" in node:
        node["radius"] = float(node["radius"]) * node_scale


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

    if result.get("dimension") == "2d":
        if result.get("kind") == "matrix":
            result["cell_size"] = values.get("cell_size", result.get("cell_size", 18))
            result["label_size"] = values.get("label_size", result.get("label_size", 260))
            result["style"]["label_scale"] = values.get("label_scale", 1.0)
            result["style"]["cell_opacity"] = values.get("cell_opacity", 0.72)
            return result

        sx = values.get("spacing_x", 1.0)
        sy = values.get("spacing_y", 1.0)
        ns = values.get("node_scale", 1.0)
        for group in result.get("groups", []):
            _scale_rect(group, sx, sy, 1.0)
        for node in result.get("nodes", []):
            _scale_rect(node, sx, sy, ns)
        bounds = result.get("bounds")
        if isinstance(bounds, dict):
            bounds["width"] = float(bounds.get("width", 1.0)) * sx
            bounds["height"] = float(bounds.get("height", 1.0)) * sy
        result["style"]["label_scale"] = values.get("label_scale", 1.0)
        result["style"]["edge_opacity"] = values.get("edge_opacity", 0.40)
        return result

    if result.get("dimension") == "3d":
        sx = values.get("scale_x", 1.0)
        sy = values.get("scale_y", 1.0)
        sz = values.get("scale_z", 1.0)
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
        extent = float(result.get("extent", 900.0))
        result["extent"] = extent * max(sx, sy, sz)
        result["style"]["node_scale"] = values.get("node_scale", 1.0)
        result["style"]["label_scale"] = values.get("label_scale", 1.0)
        result["style"]["edge_opacity"] = values.get("edge_opacity", 0.22)
        result["style"]["perspective"] = values.get("perspective", 1100)
        result["style"]["glow"] = values.get("glow", 0.65)
        result["style"]["extrusion"] = values.get("extrusion", 28)
        result["style"]["edge_glow"] = values.get("edge_glow", 0.45)
        return result

    return result
