from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_effects() -> dict[str, dict[str, Any]]:
    effects: dict[str, dict[str, Any]] = {}
    for path in sorted(ROOT.rglob("*.json")):
        if "presets" in path.parts:
            continue
        item = _load_json(path)
        if item.get("type") != "structureprojector_3d_effect":
            continue
        effect_id = str(item.get("id", ""))
        if not effect_id:
            raise ValueError(f"3D effect without id: {path}")
        if effect_id in effects:
            raise ValueError(f"Duplicate 3D effect id: {effect_id}")
        effects[effect_id] = item
    return effects


def load_groups() -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    preset_root = ROOT / "presets"
    if not preset_root.exists():
        return groups
    for path in sorted(preset_root.glob("*/group.json")):
        item = _load_json(path)
        if item.get("type") != "structureprojector_3d_effect_group":
            continue
        group_id = str(item.get("id", ""))
        if not group_id:
            raise ValueError(f"3D effect group without id: {path}")
        if group_id in groups:
            raise ValueError(f"Duplicate 3D effect group id: {group_id}")
        groups[group_id] = item
    return groups


def compile_group(group_id: str) -> dict[str, Any]:
    effects = load_effects()
    groups = load_groups()
    if group_id not in groups:
        raise KeyError(group_id)
    group = deepcopy(groups[group_id])
    controls: list[dict[str, Any]] = []
    seen: set[str] = set()
    for effect_id in group.get("effects", []):
        effect = effects.get(str(effect_id))
        if effect is None:
            raise ValueError(f"Unknown 3D effect {effect_id!r} in group {group_id!r}")
        for control in effect.get("controls", []):
            control_id = str(control.get("id"))
            if control_id in seen:
                continue
            seen.add(control_id)
            controls.append(deepcopy(control))
    values = defaults_for_controls(controls)
    values.update(deepcopy(group.get("values", {})))
    return {
        "id": group["id"],
        "title": group.get("title") or group["id"],
        "effects": list(group.get("effects", [])),
        "controls": controls,
        "values": values,
    }


def library_manifest() -> dict[str, Any]:
    effects = load_effects()
    groups = load_groups()
    return {
        "version": 1,
        "dimension": "3d",
        "root": "effects/3d",
        "effects": [deepcopy(effects[key]) for key in sorted(effects)],
        "groups": [compile_group(key) for key in sorted(groups)],
    }


def universal_controls() -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    seen: set[str] = set()
    for effect_id in sorted(load_effects()):
        effect = load_effects()[effect_id]
        for control in effect.get("controls", []):
            control_id = str(control.get("id"))
            if control_id in seen:
                continue
            seen.add(control_id)
            controls.append(deepcopy(control))
    return controls


def defaults_for_controls(controls: list[dict[str, Any]]) -> dict[str, Any]:
    return {str(c["id"]): c.get("default") for c in controls}


def universal_defaults() -> dict[str, Any]:
    return defaults_for_controls(universal_controls())


def normalize_values(supplied: dict[str, Any] | None = None) -> dict[str, Any]:
    supplied = supplied or {}
    values = universal_defaults()
    for control in universal_controls():
        control_id = str(control["id"])
        if control_id not in supplied:
            continue
        if control.get("type") != "range":
            values[control_id] = supplied[control_id]
            continue
        try:
            value = float(supplied[control_id])
        except (TypeError, ValueError):
            continue
        minimum = float(control.get("min", value))
        maximum = float(control.get("max", value))
        value = max(minimum, min(maximum, value))
        step = float(control.get("step", 0) or 0)
        if step > 0:
            value = minimum + round((value - minimum) / step) * step
        values[control_id] = value
    return values


def group_presets() -> dict[str, dict[str, Any]]:
    return {
        group_id: compile_group(group_id)["values"]
        for group_id in sorted(load_groups())
    }


def apply_universal_effects(
    projection: dict[str, Any],
    supplied: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the same 3D effect library to any mapper/projection output.

    Projection owns semantic/layout coordinates. The effect library may scale
    presentation coordinates and set renderer style, but MUST NOT create,
    remove, rename or reinterpret semantic nodes/edges.
    """
    if projection.get("dimension") != "3d":
        raise ValueError("Universal 3D effects require a 3D projection")

    result = deepcopy(projection)
    values = normalize_values(supplied)
    effects = load_effects()

    # Layout transforms are explicitly declared by effects. They are visual
    # transforms only; semantic coordinates in the source graph remain intact.
    layout_targets: dict[str, str] = {}
    style_targets: dict[str, str] = {}
    for effect_id in sorted(effects):
        effect = effects[effect_id]
        layout_targets.update({str(k): str(v) for k, v in effect.get("layout_targets", {}).items()})
        style_targets.update({str(k): str(v) for k, v in effect.get("style_targets", {}).items()})

    sx = float(values.get("scale_x", 1.0)) if layout_targets.get("scale_x") == "x" else 1.0
    sy = float(values.get("scale_y", 1.0)) if layout_targets.get("scale_y") == "y" else 1.0
    sz = float(values.get("scale_z", 1.0)) if layout_targets.get("scale_z") == "z" else 1.0

    for node in result.get("nodes", []):
        if "x" in node:
            node["x"] = float(node["x"]) * sx
        if "y" in node:
            node["y"] = float(node["y"]) * sy
        if "z" in node:
            node["z"] = float(node["z"]) * sz
    for group in result.get("groups", []):
        if "x" in group:
            group["x"] = float(group["x"]) * sx
        if "y" in group:
            group["y"] = float(group["y"]) * sy
        if "z" in group:
            group["z"] = float(group["z"]) * sz
        if "radius" in group:
            group["radius"] = float(group["radius"]) * max(sx, sz)

    if "extent" in result:
        result["extent"] = float(result["extent"]) * max(sx, sy, sz)

    style = result.setdefault("style", {})
    for control_id, target in style_targets.items():
        if control_id in values:
            style[target] = values[control_id]

    result["control_schema"] = universal_controls()
    result["control_schema_version"] = 1
    result["control_values"] = values
    result["builtin_presets"] = group_presets()
    result["effect_library"] = {
        "root": "effects/3d",
        "version": 1,
        "groups": [compile_group(group_id) for group_id in sorted(load_groups())],
        "effects": sorted(effects),
    }
    return result
