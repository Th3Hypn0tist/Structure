from __future__ import annotations

import copy
import json
import os
import tempfile
from typing import Any

from server.semantics import DEFAULT_COLOR_SPACES, DEFAULT_RULESETS, validate_color_spaces, validate_properties, validate_rulesets

DEFAULT_WORKSPACE: dict[str, Any] = {
    "version": "0.2.0",
    "entities": [],
    "rulesets": copy.deepcopy(DEFAULT_RULESETS),
    "color_spaces": copy.deepcopy(DEFAULT_COLOR_SPACES),
    "view": {"ruleset_ref": "ALL"},
    "camera": {"position": [0.0, 1.5, 8.0], "yaw": 0.0, "pitch": 0.0, "fov": 60.0},
    "settings": {
        "camera_defaults": {"position": [0.0, 1.5, 8.0], "yaw": 0.0, "pitch": 0.0, "fov": 60.0, "movement_speed": 6.0, "mouse_sensitivity": 0.0025, "near_clip": 0.05, "far_clip": 1000.0},
        "link_visualization": {"anchor_spacing": 0.28, "anchor_offset": 0.58, "base_flow_speed": 0.15, "flow_width": 0.18},
        "event_playback": {"base_link_speed": 0.15, "active_link_speed": 2.0, "effect_travel_duration": 1.2, "next_event_delay": 0.25, "fade_out_duration": 0.4, "global_playback_speed": 1.0},
    },
}

class WorkspaceStore:
    def __init__(self, path: str): self.path = path
    def load(self) -> dict[str, Any]:
        if not os.path.exists(self.path): return copy.deepcopy(DEFAULT_WORKSPACE)
        with open(self.path, "r", encoding="utf-8") as fh: data = json.load(fh)
        return self._validate(data)
    def save(self, data: dict[str, Any]) -> dict[str, Any]:
        data = self._validate(data); directory = os.path.dirname(self.path) or "."; fd, temp_path = tempfile.mkstemp(prefix="structure-", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh: json.dump(data, fh, ensure_ascii=False, indent=2); fh.write("\n")
            os.replace(temp_path, self.path)
        finally:
            if os.path.exists(temp_path): os.unlink(temp_path)
        return data
    def _validate(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict): raise ValueError("workspace must be an object")
        entities = data.setdefault("entities", [])
        if not isinstance(entities, list): raise ValueError("workspace.entities must be an array")
        seen: set[str] = set()
        for entity in entities:
            if not isinstance(entity, dict): raise ValueError("each entity must be an object")
            entity_id = entity.get("id")
            if not isinstance(entity_id, str) or not entity_id: raise ValueError("each entity requires non-empty id")
            if entity_id in seen: raise ValueError(f"duplicate entity id: {entity_id}")
            seen.add(entity_id); entity.setdefault("name", entity_id); entity.setdefault("entity_type_ref", "entity"); entity.setdefault("status", "unlocked")
            position = entity.get("position", [0, 0, 0])
            if not (isinstance(position, list) and len(position) == 3 and all(isinstance(v, (int, float)) for v in position)): raise ValueError(f"entity {entity_id} position must be [x,y,z]")
            entity["position"] = [float(v) for v in position]; entity.setdefault("properties", [])
            if not isinstance(entity["properties"], list): raise ValueError(f"entity {entity_id} properties must be an array")
        color_spaces = data.setdefault("color_spaces", copy.deepcopy(DEFAULT_COLOR_SPACES)); rulesets = data.setdefault("rulesets", copy.deepcopy(DEFAULT_RULESETS))
        if not isinstance(color_spaces, list) or not isinstance(rulesets, list): raise ValueError("workspace rulesets and color_spaces must be arrays")
        color_index = validate_color_spaces(color_spaces); ruleset_index = validate_rulesets(rulesets, color_index); validate_properties(entities, ruleset_index)
        view = data.setdefault("view", {"ruleset_ref": "ALL"}); selected_ruleset = view.get("ruleset_ref", "ALL")
        if selected_ruleset != "ALL" and selected_ruleset not in ruleset_index: raise ValueError(f"view.ruleset_ref does not resolve: {selected_ruleset}")
        camera = data.setdefault("camera", copy.deepcopy(DEFAULT_WORKSPACE["camera"])); fov = float(camera.get("fov", 60.0))
        if not 15.0 <= fov <= 170.0: raise ValueError("camera.fov must be within 15..170 degrees")
        camera["fov"] = fov
        settings = data.setdefault("settings", copy.deepcopy(DEFAULT_WORKSPACE["settings"]))
        for key, default in DEFAULT_WORKSPACE["settings"].items(): settings.setdefault(key, copy.deepcopy(default))
        data["version"] = "0.2.0"; return data
