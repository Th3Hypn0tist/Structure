from __future__ import annotations

from typing import Any


DEFAULT_COLOR_SPACES: list[dict[str, Any]] = [
    {"id": "COLORSPACE_LINK_GENERIC", "name": "Generic Link", "colors": {"base": [0.42, 0.48, 0.58], "flow": [0.78, 0.84, 0.94], "selected": [0.95, 0.97, 1.0]}},
    {"id": "COLORSPACE_DEPENDENCY", "name": "Dependency", "colors": {"base": [0.18, 0.42, 0.90], "flow": [0.40, 0.76, 1.0], "selected": [0.78, 0.92, 1.0]}},
    {"id": "COLORSPACE_OWNERSHIP", "name": "Ownership", "colors": {"base": [0.78, 0.50, 0.08], "flow": [1.0, 0.76, 0.22], "selected": [1.0, 0.90, 0.58]}},
    {"id": "COLORSPACE_AUTHORITY", "name": "Authority", "colors": {"base": [0.72, 0.18, 0.28], "flow": [1.0, 0.38, 0.42], "selected": [1.0, 0.72, 0.74]}},
    {"id": "COLORSPACE_CONTAINMENT", "name": "Containment", "colors": {"base": [0.22, 0.60, 0.32], "flow": [0.46, 0.92, 0.54], "selected": [0.74, 1.0, 0.78]}},
    {"id": "COLORSPACE_ARCHITECTURE", "name": "Architecture", "colors": {"base": [0.52, 0.26, 0.82], "flow": [0.76, 0.48, 1.0], "selected": [0.90, 0.76, 1.0]}},
    {"id": "COLORSPACE_CAUSAL", "name": "Causal", "colors": {"base": [0.78, 0.20, 0.18], "flow": [1.0, 0.48, 0.30], "selected": [1.0, 0.78, 0.64]}},
    {"id": "COLORSPACE_RELATION", "name": "Relation", "colors": {"base": [0.20, 0.62, 0.64], "flow": [0.38, 0.90, 0.92], "selected": [0.72, 1.0, 1.0]}},
]


def _link_ruleset(ruleset_id: str, name: str, link_type_ref: str, parent_role: str, child_role: str, color_space_ref: str) -> dict[str, Any]:
    return {
        "id": ruleset_id,
        "name": name,
        "property_type_ref": "link",
        "link_type_ref": link_type_ref,
        "semantic_roles": {"parent_ref": parent_role, "child_ref": child_role},
        "property_owner": "ruleset_defined",
        "color_space_ref": color_space_ref,
    }


DEFAULT_RULESETS: list[dict[str, Any]] = [
    _link_ruleset("RULESET_LINK_DEPENDENCY", "Dependency", "dependency", "dependency_target", "dependent", "COLORSPACE_DEPENDENCY"),
    _link_ruleset("RULESET_LINK_OWNERSHIP", "Ownership", "ownership", "owner", "owned", "COLORSPACE_OWNERSHIP"),
    _link_ruleset("RULESET_LINK_AUTHORITY", "Authority", "authority", "authority", "governed", "COLORSPACE_AUTHORITY"),
    _link_ruleset("RULESET_LINK_CONTAINMENT", "Containment", "containment", "container", "contained", "COLORSPACE_CONTAINMENT"),
    _link_ruleset("RULESET_LINK_ARCHITECTURE_PARENT", "Architecture Parent", "architecture_parent", "architecture_parent", "architecture_child", "COLORSPACE_ARCHITECTURE"),
    _link_ruleset("RULESET_LINK_RELATION", "Relation", "relation", "relation_parent", "relation_child", "COLORSPACE_RELATION"),
    _link_ruleset("RULESET_LINK_EVENT_READ", "Event Read", "event_read", "observed_source", "event", "COLORSPACE_CAUSAL"),
    _link_ruleset("RULESET_LINK_EVENT_INPUT", "Event Input", "event_input", "input_source", "event", "COLORSPACE_CAUSAL"),
    _link_ruleset("RULESET_LINK_EVENT_OUTPUT", "Event Output", "event_output", "event", "output_target", "COLORSPACE_CAUSAL"),
    _link_ruleset("RULESET_LINK_EVENT_EFFECT", "Event Effect", "event_effect", "event", "effect", "COLORSPACE_CAUSAL"),
    _link_ruleset("RULESET_LINK_EVENT_CAUSE", "Event Cause", "event_cause", "cause_source", "event", "COLORSPACE_CAUSAL"),
    _link_ruleset("RULESET_LINK_EVENT_CONDITION", "Event Condition", "event_condition", "condition_source", "event", "COLORSPACE_CAUSAL"),
    _link_ruleset("RULESET_LINK_EFFECT_TARGET", "Effect Target", "effect_target", "effect", "effect_target", "COLORSPACE_CAUSAL"),
    {"id": "RULESET_TYPE", "name": "Type", "property_type_ref": "type"},
    {"id": "RULESET_MOUNT", "name": "Mounted Abstraction", "property_type_ref": "mount"},
    {"id": "RULESET_EVENT", "name": "Event", "property_type_ref": "event"},
    {"id": "RULESET_EFFECT", "name": "Effect", "property_type_ref": "effect"},
    {"id": "RULESET_DATA", "name": "Data", "property_type_ref": "data"},
    {"id": "RULESET_FUNCTION", "name": "Function", "property_type_ref": "function"},
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
            if not (isinstance(value, list) and len(value) == 3 and all(isinstance(component, (int, float)) for component in value)):
                raise ValueError(f"color space {color_space['id']}.{key} must be [r,g,b]")
            if any(component < 0 or component > 1 for component in value):
                raise ValueError(f"color space {color_space['id']}.{key} components must be within 0..1")
    return index


def validate_rulesets(rulesets: list[dict[str, Any]], color_spaces: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index = index_by_id(rulesets, "ruleset")
    supported = {"type", "mount", "event", "effect", "data", "function"}
    for ruleset in rulesets:
        property_type_ref = ruleset.get("property_type_ref")
        if property_type_ref == "link":
            for field in ("link_type_ref", "semantic_roles", "property_owner", "color_space_ref"):
                if field not in ruleset:
                    raise ValueError(f"link ruleset {ruleset['id']} requires {field}")
            roles = ruleset["semantic_roles"]
            if not isinstance(roles, dict) or not roles.get("parent_ref") or not roles.get("child_ref"):
                raise ValueError(f"link ruleset {ruleset['id']} requires parent_ref and child_ref semantic roles")
            if ruleset["color_space_ref"] not in color_spaces:
                raise ValueError(f"ruleset {ruleset['id']} color_space_ref does not resolve: {ruleset['color_space_ref']}")
        elif property_type_ref not in supported:
            raise ValueError(f"ruleset {ruleset['id']} has unsupported property_type_ref: {property_type_ref}")
    return index


def _property_type(ref: str, property_index: dict[str, tuple[str, dict[str, Any]]]) -> str | None:
    item = property_index.get(ref)
    return item[1].get("property_type_ref") if item else None


def declared_type(entity: dict[str, Any]) -> str | None:
    matches = [prop for prop in entity.get("properties", []) if prop.get("property_type_ref") == "type"]
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError(f"entity {entity.get('id')} has multiple Type Properties")
    value = matches[0].get("value")
    if not isinstance(value, dict):
        raise ValueError(f"type property {matches[0].get('id')} value must be an object")
    type_ref = value.get("type_ref")
    return type_ref if isinstance(type_ref, str) and type_ref else None


def validate_properties(entities: list[dict[str, Any]], rulesets: dict[str, dict[str, Any]]) -> None:
    entity_ids = {entity["id"] for entity in entities}
    property_index: dict[str, tuple[str, dict[str, Any]]] = {}

    for entity in entities:
        type_count = 0
        for prop in entity["properties"]:
            if not isinstance(prop, dict):
                raise ValueError(f"entity {entity['id']} property must be an object")
            prop_id = prop.get("id")
            if not isinstance(prop_id, str) or not prop_id:
                raise ValueError(f"entity {entity['id']} property requires non-empty id")
            if prop_id in entity_ids or prop_id in property_index:
                raise ValueError(f"Entity/Property canonical identity collision: {prop_id}")
            if prop.get("property_type_ref") == "type":
                type_count += 1
            property_index[prop_id] = (entity["id"], prop)
        if type_count > 1:
            raise ValueError(f"entity {entity['id']} has multiple Type Properties")

    canonical_ids = entity_ids | set(property_index)
    for owner_id, prop in property_index.values():
        prop_id = prop["id"]
        property_type_ref = prop.get("property_type_ref")
        ruleset_ref = prop.get("ruleset_ref")
        if not isinstance(property_type_ref, str) or not property_type_ref:
            raise ValueError(f"property {prop_id} requires property_type_ref")
        if not isinstance(ruleset_ref, str) or ruleset_ref not in rulesets:
            raise ValueError(f"property {prop_id} ruleset_ref does not resolve: {ruleset_ref}")
        ruleset = rulesets[ruleset_ref]
        if ruleset.get("property_type_ref") != property_type_ref:
            raise ValueError(f"property {prop_id} type {property_type_ref} does not match ruleset {ruleset_ref}")
        value = prop.get("value")
        if not isinstance(value, dict):
            raise ValueError(f"property {prop_id} value must be an object")

        if property_type_ref == "type":
            type_ref = value.get("type_ref")
            if not isinstance(type_ref, str) or not type_ref:
                raise ValueError(f"type property {prop_id} requires type_ref")
            if not isinstance(value.get("properties"), dict):
                raise ValueError(f"type property {prop_id} value.properties must be an object")

        elif property_type_ref == "mount":
            abstraction_ref = value.get("abstraction_ref")
            if not isinstance(abstraction_ref, str) or not abstraction_ref:
                raise ValueError(f"mount property {prop_id} requires abstraction_ref")
            if not isinstance(value.get("properties"), dict):
                raise ValueError(f"mount property {prop_id} value.properties must be an object")

        elif property_type_ref == "link":
            parent_ref = value.get("parent_ref")
            child_ref = value.get("child_ref")
            if parent_ref not in canonical_ids:
                raise ValueError(f"property {prop_id} parent_ref does not resolve: {parent_ref}")
            if child_ref not in canonical_ids:
                raise ValueError(f"property {prop_id} child_ref does not resolve: {child_ref}")
            if value.get("link_type_ref") != ruleset.get("link_type_ref"):
                raise ValueError(f"property {prop_id} link_type_ref does not match ruleset {ruleset_ref}")
            if "target_ref" in value or "dependency_type" in value:
                raise ValueError(f"property {prop_id} duplicates canonical endpoint semantics")
            if not isinstance(value.get("properties"), dict):
                raise ValueError(f"property {prop_id} value.properties must be an object")

            link_type_ref = value["link_type_ref"]
            parent_type = _property_type(parent_ref, property_index)
            child_type = _property_type(child_ref, property_index)
            if link_type_ref == "event_effect" and (parent_type != "event" or child_type != "effect"):
                raise ValueError(f"property {prop_id} event_effect endpoints must be Event -> Effect")
            if link_type_ref == "effect_target" and parent_type != "effect":
                raise ValueError(f"property {prop_id} effect_target parent_ref must be Effect")
            if link_type_ref in {"event_read", "event_input", "event_cause", "event_condition"} and child_type != "event":
                raise ValueError(f"property {prop_id} {link_type_ref} child_ref must be Event")
            if link_type_ref == "event_output" and parent_type != "event":
                raise ValueError(f"property {prop_id} event_output parent_ref must be Event")

        elif property_type_ref == "event":
            event_type_ref = value.get("event_type_ref")
            if not isinstance(event_type_ref, str) or not event_type_ref:
                raise ValueError(f"event property {prop_id} requires event_type_ref")
            for forbidden in ("reads", "inputs", "outputs", "effects", "causes", "conditions", "targets"):
                if forbidden in value:
                    raise ValueError(f"event property {prop_id} embeds authoritative directed reference: {forbidden}")
            if not isinstance(value.get("properties"), dict):
                raise ValueError(f"event property {prop_id} value.properties must be an object")

        elif property_type_ref == "effect":
            effect_type_ref = value.get("effect_type_ref")
            if not isinstance(effect_type_ref, str) or not effect_type_ref:
                raise ValueError(f"effect property {prop_id} requires effect_type_ref")
            if "target_ref" in value or "targets" in value:
                raise ValueError(f"effect property {prop_id} embeds authoritative target reference")
            if not isinstance(value.get("properties"), dict):
                raise ValueError(f"effect property {prop_id} value.properties must be an object")

        elif property_type_ref == "data":
            data_type_ref = value.get("data_type_ref")
            if not isinstance(data_type_ref, str) or not data_type_ref:
                raise ValueError(f"data property {prop_id} requires data_type_ref")
            if not isinstance(value.get("properties"), dict):
                raise ValueError(f"data property {prop_id} value.properties must be an object")

        elif property_type_ref == "function":
            function_type_ref = value.get("function_type_ref")
            if not isinstance(function_type_ref, str) or not function_type_ref:
                raise ValueError(f"function property {prop_id} requires function_type_ref")
            if not isinstance(value.get("properties"), dict):
                raise ValueError(f"function property {prop_id} value.properties must be an object")
            for field in ("input_refs", "output_refs"):
                refs = value.get(field)
                if refs is None:
                    continue
                if not isinstance(refs, list) or any(ref not in canonical_ids for ref in refs):
                    raise ValueError(f"function property {prop_id} {field} must resolve canonical identities")

        metadata = prop.get("metadata")
        if metadata is not None:
            if not isinstance(metadata, dict):
                raise ValueError(f"property {prop_id} metadata must be an object")
            workspace_entity_ref = metadata.get("workspace_entity_ref")
            if workspace_entity_ref is not None and workspace_entity_ref != owner_id:
                raise ValueError(f"property {prop_id} metadata.workspace_entity_ref must equal canonical owner {owner_id}")
