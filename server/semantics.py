from __future__ import annotations

from typing import Any


DEFAULT_COLOR_SPACES: list[dict[str, Any]] = [
    {
        "id": "COLORSPACE_LINK_GENERIC",
        "name": "Generic Link",
        "colors": {
            "base": [0.42, 0.48, 0.58],
            "flow": [0.78, 0.84, 0.94],
            "selected": [0.95, 0.97, 1.0],
        },
    },
    {
        "id": "COLORSPACE_DEPENDENCY",
        "name": "Dependency",
        "colors": {
            "base": [0.18, 0.42, 0.90],
            "flow": [0.40, 0.76, 1.0],
            "selected": [0.78, 0.92, 1.0],
        },
    },
    {
        "id": "COLORSPACE_OWNERSHIP",
        "name": "Ownership",
        "colors": {
            "base": [0.78, 0.50, 0.08],
            "flow": [1.0, 0.76, 0.22],
            "selected": [1.0, 0.90, 0.58],
        },
    },
    {
        "id": "COLORSPACE_AUTHORITY",
        "name": "Authority",
        "colors": {
            "base": [0.72, 0.18, 0.28],
            "flow": [1.0, 0.38, 0.42],
            "selected": [1.0, 0.72, 0.74],
        },
    },
    {
        "id": "COLORSPACE_CONTAINMENT",
        "name": "Containment",
        "colors": {
            "base": [0.22, 0.60, 0.32],
            "flow": [0.46, 0.92, 0.54],
            "selected": [0.74, 1.0, 0.78],
        },
    },
    {
        "id": "COLORSPACE_ARCHITECTURE",
        "name": "Architecture",
        "colors": {
            "base": [0.52, 0.26, 0.82],
            "flow": [0.76, 0.48, 1.0],
            "selected": [0.90, 0.76, 1.0],
        },
    },
]


DEFAULT_RULESETS: list[dict[str, Any]] = [
    {
        "id": "RULESET_DEPENDENCY",
        "name": "Dependency",
        "property_type_ref": "link",
        "link_type_ref": "dependency",
        "parent_role": "dependency",
        "child_role": "dependent",
        "color_space_ref": "COLORSPACE_DEPENDENCY",
    },
    {
        "id": "RULESET_OWNERSHIP",
        "name": "Ownership",
        "property_type_ref": "link",
        "link_type_ref": "ownership",
        "parent_role": "owner",
        "child_role": "owned",
        "color_space_ref": "COLORSPACE_OWNERSHIP",
    },
    {
        "id": "RULESET_AUTHORITY",
        "name": "Authority",
        "property_type_ref": "link",
        "link_type_ref": "authority",
        "parent_role": "authority",
        "child_role": "governed",
        "color_space_ref": "COLORSPACE_AUTHORITY",
    },
    {
        "id": "RULESET_CONTAINMENT",
        "name": "Containment",
        "property_type_ref": "link",
        "link_type_ref": "containment",
        "parent_role": "container",
        "child_role": "contained",
        "color_space_ref": "COLORSPACE_CONTAINMENT",
    },
    {
        "id": "RULESET_ARCHITECTURE",
        "name": "Architecture",
        "property_type_ref": "link",
        "link_type_ref": "architecture_parent",
        "parent_role": "architecture_parent",
        "child_role": "architecture_child",
        "color_space_ref": "COLORSPACE_ARCHITECTURE",
    },
]


def index_by_id(items: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"each {label} must be an object")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError(f"each {label} requires non-empty id")
        if item_id in result:
            raise ValueError(f"duplicate {label} id: {item_id}")
        result[item_id] = item
    return result


def validate_color_spaces(color_spaces: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index = index_by_id(color_spaces, "color space")
    for color_space in color_spaces:
        colors = color_space.get("colors")
        if not isinstance(colors, dict):
            raise ValueError(f"color space {color_space['id']} requires colors object")
        for key in ("base", "flow", "selected"):
            value = colors.get(key)
            if not (
                isinstance(value, list)
                and len(value) == 3
                and all(isinstance(component, (int, float)) for component in value)
            ):
                raise ValueError(f"color space {color_space['id']}.{key} must be [r,g,b]")
            colors[key] = [float(component) for component in value]
    return index


def validate_rulesets(
    rulesets: list[dict[str, Any]],
    color_spaces: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    index = index_by_id(rulesets, "ruleset")
    for ruleset in rulesets:
        property_type_ref = ruleset.get("property_type_ref")
        if not isinstance(property_type_ref, str) or not property_type_ref:
            raise ValueError(f"ruleset {ruleset['id']} requires property_type_ref")
        if property_type_ref == "link":
            for field in ("link_type_ref", "parent_role", "child_role"):
                value = ruleset.get(field)
                if not isinstance(value, str) or not value:
                    raise ValueError(f"link ruleset {ruleset['id']} requires {field}")
        color_space_ref = ruleset.get("color_space_ref")
        if color_space_ref is not None and color_space_ref not in color_spaces:
            raise ValueError(
                f"ruleset {ruleset['id']} color_space_ref does not resolve: {color_space_ref}"
            )
    return index


def validate_properties(
    entities: list[dict[str, Any]],
    rulesets: dict[str, dict[str, Any]],
) -> None:
    entity_ids = {entity["id"] for entity in entities}
    property_ids: set[str] = set()

    for entity in entities:
        properties = entity.get("properties", [])
        for prop in properties:
            if not isinstance(prop, dict):
                raise ValueError(f"entity {entity['id']} property must be an object")
            prop_id = prop.get("id")
            if not isinstance(prop_id, str) or not prop_id:
                raise ValueError(f"entity {entity['id']} property requires non-empty id")
            if prop_id in property_ids:
                raise ValueError(f"duplicate property id: {prop_id}")
            property_ids.add(prop_id)

            property_type_ref = prop.get("property_type_ref")
            ruleset_ref = prop.get("ruleset_ref")
            if not isinstance(property_type_ref, str) or not property_type_ref:
                raise ValueError(f"property {prop_id} requires property_type_ref")
            if not isinstance(ruleset_ref, str) or ruleset_ref not in rulesets:
                raise ValueError(f"property {prop_id} ruleset_ref does not resolve: {ruleset_ref}")

            ruleset = rulesets[ruleset_ref]
            if ruleset.get("property_type_ref") != property_type_ref:
                raise ValueError(
                    f"property {prop_id} type {property_type_ref} does not match ruleset {ruleset_ref}"
                )

            prop.setdefault("status", "unlocked")
            value = prop.get("value")
            if not isinstance(value, dict):
                raise ValueError(f"property {prop_id} value must be an object")

            if property_type_ref == "link":
                parent_ref = value.get("parent_ref")
                child_ref = value.get("child_ref")
                if parent_ref not in entity_ids:
                    raise ValueError(f"property {prop_id} parent_ref does not resolve: {parent_ref}")
                if child_ref not in entity_ids:
                    raise ValueError(f"property {prop_id} child_ref does not resolve: {child_ref}")
                expected_link_type = ruleset.get("link_type_ref")
                actual_link_type = value.get("link_type_ref")
                if actual_link_type != expected_link_type:
                    raise ValueError(
                        f"property {prop_id} link_type_ref {actual_link_type} does not match ruleset {ruleset_ref}"
                    )
                value.setdefault("properties", {})
                if not isinstance(value["properties"], dict):
                    raise ValueError(f"property {prop_id} value.properties must be an object")
