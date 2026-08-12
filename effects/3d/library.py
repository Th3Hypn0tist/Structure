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
        effects[str(item["id"])] = item
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
        groups[str(item["id"])] = item
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
    return {
        "id": group["id"],
        "title": group.get("title") or group["id"],
        "effects": list(group.get("effects", [])),
        "controls": controls,
        "values": deepcopy(group.get("values", {})),
    }


def library_manifest() -> dict[str, Any]:
    effects = load_effects()
    groups = load_groups()
    return {
        "version": 1,
        "dimension": "3d",
        "effects": [deepcopy(effects[key]) for key in sorted(effects)],
        "groups": [compile_group(key) for key in sorted(groups)],
    }


def universal_controls() -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    seen: set[str] = set()
    for effect in load_effects().values():
        for control in effect.get("controls", []):
            control_id = str(control.get("id"))
            if control_id in seen:
                continue
            seen.add(control_id)
            controls.append(deepcopy(control))
    return controls


def universal_defaults() -> dict[str, Any]:
    return {str(c["id"]): c.get("default") for c in universal_controls()}
