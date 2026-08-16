from __future__ import annotations

import copy
import json
import os
import tempfile
from typing import Any

from server.semantics import DEFAULT_COLOR_SPACES, DEFAULT_RULESETS, validate_color_spaces, validate_properties, validate_rulesets
from server.starting_scene import starting_entities

WORKSPACE_VERSION = "0.3.0"

DEFAULT_WORKSPACE: dict[str, Any] = {
    "version": WORKSPACE_VERSION,
    "entities": [],
    "rulesets": copy.deepcopy(DEFAULT_RULESETS),
    "color_spaces": copy.deepcopy(DEFAULT_COLOR_SPACES),
    "camera": {
        "position": [0.0, 1.5, 16.0],
        "reference": [0.0, 0.0, 0.0],
        "yaw": 0.0,
        "pitch": 0.0,
        "fov": 60.0,
    },
    "settings": {
        "camera_defaults": {
            "position": [0.0, 1.5, 16.0],
            "reference": [0.0, 0.0, 0.0],
            "yaw": 0.0,
            "pitch": 0.0,
            "fov": 60.0,
            "movement_speed": 6.0,
            "mouse_sensitivity": 0.0025,
            "wheel_zoom_speed": 0.15,
            "drag_pan_speed": 0.01,
            "near_clip": 0.05,
            "far_clip": 1000.0,
        },
        "link_visualization": {
            "anchor_spacing": 0.28,
            "anchor_offset": 0.58,
            "base_flow_speed": 0.15,
            "flow_width": 0.18,
        },
        "event_playback": {
            "active_link_speed": 2.0,
            "effect_travel_duration": 1.2,
        },
        "view_defaults": {
            "ruleset_ref": "ALL",
            "node_master_size": 1.0,
            "grid_visible": True,
            "snap_to_grid": True,
            "grid_size": 1.0,
            "property_panel_size": 1.0,
            "property_panel_collapsed": {},
            "show_all_props": False,
            "entity_info_collapsed": {},
            "hidden_link_types": {},
            "event_routes_visible": True,
        },
    },
}


def starting_workspace() -> dict[str, Any]:
    workspace = copy.deepcopy(DEFAULT_WORKSPACE)
    workspace["entities"] = starting_entities()
    return workspace


def _require_object(parent: dict[str, Any], field: str, context: str) -> dict[str, Any]:
    value = parent.get(field)
    if not isinstance(value, dict):
        raise ValueError(f"{context}.{field} must be an object")
    return value


def _require_array(parent: dict[str, Any], field: str, context: str) -> list[Any]:
    value = parent.get(field)
    if not isinstance(value, list):
        raise ValueError(f"{context}.{field} must be an array")
    return value


def _require_number(parent: dict[str, Any], field: str, context: str) -> float:
    value = parent.get(field)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{context}.{field} must be numeric")
    return float(value)


def _require_vector(parent: dict[str, Any], field: str, context: str) -> list[float]:
    value = parent.get(field)
    if not (isinstance(value, list) and len(value) == 3 and all(isinstance(item, (int, float)) for item in value)):
        raise ValueError(f"{context}.{field} must be [x,y,z]")
    return [float(item) for item in value]


def _validate_entity(entity: dict[str, Any]) -> None:
    entity_id = entity.get("id")
    if not isinstance(entity_id, str) or not entity_id:
        raise ValueError("each entity requires non-empty id")
    if "entity_type_ref" in entity:
        raise ValueError(f"entity {entity_id} uses removed legacy field entity_type_ref; declare TYPE as a Property")
    name = entity.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"entity {entity_id} requires non-empty name")
    entity["position"] = _require_vector(entity, "position", f"entity {entity_id}")
    properties = _require_array(entity, "properties", f"entity {entity_id}")
    if "description" in entity and not isinstance(entity["description"], str):
        raise ValueError(f"entity {entity_id}.description must be a string")
    if "contract" in entity:
        contract = _require_object(entity, "contract", f"entity {entity_id}")
        human = contract.get("human")
        if human is not None and not isinstance(human, str):
            raise ValueError(f"entity {entity_id}.contract.human must be a string")
        revision = contract.get("human_revision")
        if revision is not None and (not isinstance(revision, int) or revision < 0):
            raise ValueError(f"entity {entity_id}.contract.human_revision must be a non-negative integer")
        machine = contract.get("machine")
        if machine is not None:
            if not isinstance(machine, dict):
                raise ValueError(f"entity {entity_id}.contract.machine must be an object")
            status = machine.get("status")
            if status not in {None, "not_generated", "needs_generation", "synchronized"}:
                raise ValueError(f"entity {entity_id}.contract.machine.status is invalid: {status}")
            generated_from = machine.get("generated_from_human_revision")
            if generated_from is not None and (not isinstance(generated_from, int) or generated_from < 0):
                raise ValueError(f"entity {entity_id}.contract.machine.generated_from_human_revision must be null or non-negative integer")
            if status == "synchronized" and generated_from != revision:
                raise ValueError(f"entity {entity_id} synchronized machine contract must match current human revision")
    for prop in properties:
        if not isinstance(prop, dict):
            raise ValueError(f"entity {entity_id} property must be an object")


def _validate_settings(settings: dict[str, Any], ruleset_index: dict[str, dict[str, Any]]) -> None:
    camera = _require_object(settings, "camera_defaults", "settings")
    for field in ("position", "reference"):
        camera[field] = _require_vector(camera, field, "settings.camera_defaults")
    for field in ("yaw", "pitch", "fov", "movement_speed", "mouse_sensitivity", "wheel_zoom_speed", "drag_pan_speed", "near_clip", "far_clip"):
        camera[field] = _require_number(camera, field, "settings.camera_defaults")
    if not 15.0 <= camera["fov"] <= 170.0:
        raise ValueError("settings.camera_defaults.fov must be within 15..170 degrees")

    links = _require_object(settings, "link_visualization", "settings")
    for field in ("anchor_spacing", "anchor_offset", "base_flow_speed", "flow_width"):
        links[field] = _require_number(links, field, "settings.link_visualization")

    event = _require_object(settings, "event_playback", "settings")
    for field in ("active_link_speed", "effect_travel_duration"):
        event[field] = _require_number(event, field, "settings.event_playback")

    view = _require_object(settings, "view_defaults", "settings")
    selected_ruleset = view.get("ruleset_ref")
    if selected_ruleset != "ALL" and selected_ruleset not in ruleset_index:
        raise ValueError(f"settings.view_defaults.ruleset_ref does not resolve: {selected_ruleset}")
    for field in ("node_master_size", "grid_size", "property_panel_size"):
        view[field] = _require_number(view, field, "settings.view_defaults")
    for field in ("grid_visible", "snap_to_grid", "show_all_props", "event_routes_visible"):
        if not isinstance(view.get(field), bool):
            raise ValueError(f"settings.view_defaults.{field} must be boolean")
    for field in ("property_panel_collapsed", "entity_info_collapsed", "hidden_link_types"):
        if not isinstance(view.get(field), dict):
            raise ValueError(f"settings.view_defaults.{field} must be an object")


class WorkspaceStore:
    def __init__(self, path: str):
        self.path = path

    def load(self) -> dict[str, Any]:
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"workspace not found: {self.path}")
        with open(self.path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return self._validate(data)

    def save(self, data: dict[str, Any]) -> dict[str, Any]:
        data = self._validate(data)
        directory = os.path.dirname(self.path) or "."
        fd, temp_path = tempfile.mkstemp(prefix="structure-", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            os.replace(temp_path, self.path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        return data

    def _validate(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError("workspace must be an object")
        if data.get("version") != WORKSPACE_VERSION:
            raise ValueError(f"workspace.version must be exactly {WORKSPACE_VERSION}; no legacy migration is performed")

        entities = _require_array(data, "entities", "workspace")
        rulesets = _require_array(data, "rulesets", "workspace")
        color_spaces = _require_array(data, "color_spaces", "workspace")
        camera = _require_object(data, "camera", "workspace")
        settings = _require_object(data, "settings", "workspace")
        if "view" in data:
            raise ValueError("workspace.view is removed; active projection belongs to settings.view_defaults.ruleset_ref")

        seen: set[str] = set()
        for entity in entities:
            if not isinstance(entity, dict):
                raise ValueError("each entity must be an object")
            _validate_entity(entity)
            if entity["id"] in seen:
                raise ValueError(f"duplicate entity id: {entity['id']}")
            seen.add(entity["id"])

        color_index = validate_color_spaces(color_spaces)
        ruleset_index = validate_rulesets(rulesets, color_index)
        validate_properties(entities, ruleset_index)

        camera["position"] = _require_vector(camera, "position", "camera")
        camera["reference"] = _require_vector(camera, "reference", "camera")
        for field in ("yaw", "pitch", "fov"):
            camera[field] = _require_number(camera, field, "camera")
        if not 15.0 <= camera["fov"] <= 170.0:
            raise ValueError("camera.fov must be within 15..170 degrees")

        _validate_settings(settings, ruleset_index)
        return data
