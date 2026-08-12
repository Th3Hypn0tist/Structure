from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

FORMAT = "STRUCTUREPROJECTOR_PRIMITIVE_REGISTRY"
VERSION = "1.1"

BASE_DIR = os.path.dirname(__file__)
REGISTRY_PATH = os.path.join(BASE_DIR, "primitives", "registry.json")


class PrimitiveRegistryError(ValueError):
    pass


def validate_registry(registry: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if registry.get("format") != FORMAT:
        errors.append({"id": "SP_PRIMITIVE_FORMAT", "message": f"Expected {FORMAT}"})
    if registry.get("version") != VERSION:
        errors.append({"id": "SP_PRIMITIVE_VERSION", "message": f"Expected primitive registry version {VERSION}"})
    primitives = registry.get("primitives")
    if not isinstance(primitives, dict) or not primitives:
        errors.append({"id": "SP_PRIMITIVE_DEFINITIONS", "message": "primitives must be a non-empty object"})
        return errors
    for required in (registry.get("fallback_node"), registry.get("fallback_connection")):
        if not isinstance(required, str) or required not in primitives:
            errors.append({"id": "SP_PRIMITIVE_FALLBACK", "message": f"Unresolved primitive fallback: {required}"})
    for primitive_id, definition in primitives.items():
        if not isinstance(definition, dict):
            errors.append({"id": "SP_PRIMITIVE_DEFINITION", "message": f"Primitive {primitive_id} must be an object"})
            continue
        geometry = definition.get("geometry")
        if not isinstance(geometry, dict) or not geometry.get("shape"):
            errors.append({"id": "SP_PRIMITIVE_GEOMETRY", "message": f"Primitive {primitive_id} requires geometry.shape"})
    return errors


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    with open(REGISTRY_PATH, "r", encoding="utf-8") as handle:
        registry = json.load(handle)
    errors = validate_registry(registry)
    if errors:
        raise PrimitiveRegistryError("; ".join(error["message"] for error in errors))
    return registry


def resolve_primitive(primitive_ref: str | None, *, connection: bool = False) -> tuple[str, dict[str, Any]]:
    registry = load_registry()
    primitives = registry["primitives"]
    fallback_key = "fallback_connection" if connection else "fallback_node"
    resolved = primitive_ref if isinstance(primitive_ref, str) and primitive_ref in primitives else registry[fallback_key]
    return resolved, primitives[resolved]
