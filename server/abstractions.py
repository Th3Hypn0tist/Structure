from __future__ import annotations

import json
import os
import re
import tempfile
from typing import Any

from server.semantics import validate_color_spaces, validate_properties, validate_rulesets

ABSTRACTION_VERSION = "1.0.0"
_ID = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


class AbstractionLibrary:
    def __init__(self, directory: str):
        self.directory = directory

    def _path(self, abstraction_id: str) -> str:
        if not isinstance(abstraction_id, str) or not _ID.fullmatch(abstraction_id):
            raise ValueError("abstraction id must match ^[A-Z][A-Z0-9_]{0,127}$")
        return os.path.join(self.directory, f"{abstraction_id}.json")

    def list(self) -> list[dict[str, str]]:
        if not os.path.isdir(self.directory):
            return []
        result: list[dict[str, str]] = []
        for filename in sorted(os.listdir(self.directory)):
            if not filename.endswith(".json"):
                raise ValueError(f"unsupported file in Abstraction Library: {filename}")
            path = os.path.join(self.directory, filename)
            with open(path, "r", encoding="utf-8") as fh:
                abstraction = self._validate(json.load(fh))
            result.append({"id": abstraction["id"], "name": abstraction["name"], "version": abstraction["version"]})
        return result

    def get(self, abstraction_id: str) -> dict[str, Any]:
        path = self._path(abstraction_id)
        if not os.path.exists(path):
            raise FileNotFoundError(f"abstraction not found: {abstraction_id}")
        with open(path, "r", encoding="utf-8") as fh:
            return self._validate(json.load(fh))

    def publish(self, abstraction: dict[str, Any]) -> dict[str, Any]:
        abstraction = self._validate(abstraction)
        path = self._path(abstraction["id"])
        os.makedirs(self.directory, exist_ok=True)
        if os.path.exists(path):
            raise FileExistsError(f"abstraction already published: {abstraction['id']}")
        fd, temp_path = tempfile.mkstemp(prefix="abstraction-", suffix=".json", dir=self.directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(abstraction, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            os.replace(temp_path, path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        return abstraction

    def _validate(self, abstraction: Any) -> dict[str, Any]:
        if not isinstance(abstraction, dict):
            raise ValueError("abstraction must be an object")
        if abstraction.get("version") != ABSTRACTION_VERSION:
            raise ValueError(f"abstraction.version must be exactly {ABSTRACTION_VERSION}")
        abstraction_id = abstraction.get("id")
        self._path(abstraction_id)
        name = abstraction.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"abstraction {abstraction_id} requires non-empty name")
        allowed = {"version", "id", "name", "entities", "rulesets", "color_spaces"}
        extra = set(abstraction) - allowed
        if extra:
            raise ValueError(f"abstraction {abstraction_id} has unsupported fields: {sorted(extra)}")

        entities = abstraction.get("entities")
        rulesets = abstraction.get("rulesets")
        color_spaces = abstraction.get("color_spaces")
        if not isinstance(entities, list):
            raise ValueError(f"abstraction {abstraction_id}.entities must be an array")
        if not isinstance(rulesets, list) or not isinstance(color_spaces, list):
            raise ValueError(f"abstraction {abstraction_id} requires rulesets and color_spaces arrays")

        entity_ids: set[str] = set()
        for entity in entities:
            if not isinstance(entity, dict):
                raise ValueError(f"abstraction {abstraction_id} entity must be an object")
            entity_id = entity.get("id")
            if not isinstance(entity_id, str) or not entity_id:
                raise ValueError(f"abstraction {abstraction_id} entity requires non-empty id")
            if entity_id in entity_ids:
                raise ValueError(f"duplicate entity id: {entity_id}")
            entity_ids.add(entity_id)
            if "entity_type_ref" in entity:
                raise ValueError(f"entity {entity_id} uses removed legacy field entity_type_ref; declare TYPE as a Property")
            entity_name = entity.get("name")
            if not isinstance(entity_name, str) or not entity_name.strip():
                raise ValueError(f"entity {entity_id} requires non-empty name")
            position = entity.get("position")
            if not (isinstance(position, list) and len(position) == 3 and all(isinstance(value, (int, float)) for value in position)):
                raise ValueError(f"entity {entity_id} position must be [x,y,z]")
            if not isinstance(entity.get("properties"), list):
                raise ValueError(f"entity {entity_id} properties must be an array")

        color_index = validate_color_spaces(color_spaces)
        ruleset_index = validate_rulesets(rulesets, color_index)
        validate_properties(entities, ruleset_index)
        return abstraction
