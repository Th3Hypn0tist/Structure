from __future__ import annotations

"""Executable CW test oracle.

This module is deliberately *not* the authoritative CW specification. The
project conversations remain authoritative. This file only centralizes the
locked rules that the automated test suite currently proves, so individual
unit tests cannot silently invent incompatible assumptions.
"""

import copy
from typing import Any

from server.semantics import DEFAULT_COLOR_SPACES, DEFAULT_RULESETS
from server.workspace import DEFAULT_WORKSPACE

# Every requirement registered here must be named by at least one test in the
# coverage manifest. Adding a locked CW rule without adding executable coverage
# therefore fails the startup conformance gate.
CW_REQUIREMENTS = {
    "CW-001": "Entity and Property identities share one canonical namespace.",
    "CW-002": "Missing meaning is unresolved/incomplete, never guessed from names or shape.",
    "CW-003": "Every declared Property has an explicit Property type and matching Ruleset.",
    "CW-004": "CW supports Type, Mount, Link, Event, Effect, Data and Function Properties.",
    "CW-005": "Every canonical reference used by a contract resolves to a canonical identity.",
    "CW-006": "Directed semantics have one authority: Link Properties, not embedded duplicate references.",
    "CW-007": "Link semantic roles and direction are defined by Rulesets.",
    "CW-008": "Event -> Effect -> target causal direction is validated explicitly.",
    "CW-009": "Function inputs and outputs are canonical references.",
    "CW-010": "Mount composes by abstraction reference; it does not copy authoritative source.",
    "CW-011": "Ruleset and ColorSpace identities resolve and malformed catalogs are rejected.",
    "CW-012": "Technical invalidity is rejected while missing optional semantics may remain incomplete.",
    "CW-013": "Save/load preserves canonical semantic identity and content without migration or inference.",
    "CW-014": "Semantic export contains canonical semantic source only, not camera/view/runtime authority.",
    "CW-015": "Abstraction publish/get preserves semantic source and rejects view/runtime authority.",
    "CW-016": "Projection is derived representation and must not mutate or multiply canonical semantics.",
    "CW-017": "Multiple canonical Links may aggregate visually while remaining distinct canonical contracts.",
    "CW-018": "Scene Event/Props representation is derived from canonical Property types.",
    "CW-019": "Scene representation is world-space 3D; DOM is editor/application chrome only.",
    "CW-020": "Event IN/OUT are one shared tiny projection point pair per Entity, independent of Event count.",
    "CW-021": "Event playback is transient runtime state and never semantic authority.",
    "CW-022": "Event animation follows canonical causal Links only; it never invents routes.",
    "CW-023": "Concurrent Event traces remain independent transient projections and fade back to baseline.",
    "CW-024": "Ruleset selection/filtering changes projection, not canonical model identity.",
    "CW-025": "Human-readable contract is source; synchronized machine-readable form must match its revision.",
    "CW-026": "Legacy/parallel semantic fields and silent compatibility migration are rejected loudly.",
    "CW-027": "All browser modules referenced by Structure are served by the application.",
    "CW-028": "Normal CW authoring has explicit UI paths for every supported CW Property primitive.",
    "CW-029": "Canonical Event editing writes canonical Event/Effect/Link Properties, never a parallel Event model.",
    "CW-030": "Canonical semantic source is Entity + Properties + Rulesets; visual state never becomes semantic authority.",
}

CW_PROPERTY_TYPES = frozenset({"type", "mount", "link", "event", "effect", "data", "function"})
CW_CAUSAL_LINK_TYPES = frozenset({"event_read", "event_input", "event_output", "event_effect", "event_cause", "event_condition", "effect_target"})
CW_GENERIC_LINK_TYPES = frozenset({"dependency", "ownership", "authority", "containment", "architecture_parent", "relation"})
CW_LINK_TYPES = CW_CAUSAL_LINK_TYPES | CW_GENERIC_LINK_TYPES

CW_LINK_ROLES = {
    "dependency": ("dependency_target", "dependent"),
    "ownership": ("owner", "owned"),
    "authority": ("authority", "governed"),
    "containment": ("container", "contained"),
    "architecture_parent": ("architecture_parent", "architecture_child"),
    "relation": ("relation_parent", "relation_child"),
    "event_read": ("observed_source", "event"),
    "event_input": ("input_source", "event"),
    "event_output": ("event", "output_target"),
    "event_effect": ("event", "effect"),
    "event_cause": ("cause_source", "event"),
    "event_condition": ("condition_source", "event"),
    "effect_target": ("effect", "effect_target"),
}

CW_VALUE_TYPE_FIELDS = {
    "type": "type_ref",
    "mount": "abstraction_ref",
    "event": "event_type_ref",
    "effect": "effect_type_ref",
    "data": "data_type_ref",
    "function": "function_type_ref",
}
CW_EVENT_FORBIDDEN_DIRECTED_FIELDS = frozenset({"reads", "inputs", "outputs", "effects", "causes", "conditions", "targets"})
CW_EFFECT_FORBIDDEN_DIRECTED_FIELDS = frozenset({"target_ref", "targets"})
CW_LINK_FORBIDDEN_DUPLICATE_FIELDS = frozenset({"target_ref", "dependency_type"})
CW_SEMANTIC_EXPORT_KEYS = frozenset({"version", "entities", "rulesets", "color_spaces"})
CW_VIEW_RUNTIME_KEYS = frozenset({"camera", "settings", "view", "runtime", "projection", "playback"})
CW_SCENE_PROPERTY_TYPES = frozenset({"effect", "data", "function", "type", "mount"})
CW_EVENT_IO_POINT_SCALE = 0.10


def workspace_fixture() -> dict[str, Any]: return copy.deepcopy(DEFAULT_WORKSPACE)
def ruleset_fixture() -> list[dict[str, Any]]: return copy.deepcopy(DEFAULT_RULESETS)
def color_space_fixture() -> list[dict[str, Any]]: return copy.deepcopy(DEFAULT_COLOR_SPACES)


def property_record(prop_id: str, property_type_ref: str, ruleset_ref: str, value: dict[str, Any], *, status: str = "unlocked") -> dict[str, Any]:
    return {"id": prop_id, "property_type_ref": property_type_ref, "ruleset_ref": ruleset_ref, "status": status, "value": copy.deepcopy(value)}


def entity_record(entity_id: str, name: str | None = None, *, position: list[float] | None = None, properties: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"id": entity_id, "name": name or entity_id, "position": list(position or [0.0, 0.0, 0.0]), "properties": copy.deepcopy(properties or [])}


def type_property(prop_id: str = "TYPE_A", type_ref: str = "service") -> dict[str, Any]: return property_record(prop_id, "type", "RULESET_TYPE", {"type_ref": type_ref, "properties": {}})
def data_property(prop_id: str = "DATA_A", data_type_ref: str = "string") -> dict[str, Any]: return property_record(prop_id, "data", "RULESET_DATA", {"data_type_ref": data_type_ref, "properties": {}})

def function_property(prop_id: str = "FUNCTION_A", function_type_ref: str = "command", *, input_refs: list[str] | None = None, output_refs: list[str] | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"function_type_ref": function_type_ref, "properties": {}}
    if input_refs is not None: value["input_refs"] = list(input_refs)
    if output_refs is not None: value["output_refs"] = list(output_refs)
    return property_record(prop_id, "function", "RULESET_FUNCTION", value)


def event_property(prop_id: str = "EVENT_A", event_type_ref: str = "changed") -> dict[str, Any]: return property_record(prop_id, "event", "RULESET_EVENT", {"event_type_ref": event_type_ref, "properties": {}})
def effect_property(prop_id: str = "EFFECT_A", effect_type_ref: str = "set") -> dict[str, Any]: return property_record(prop_id, "effect", "RULESET_EFFECT", {"effect_type_ref": effect_type_ref, "properties": {}})
def mount_property(prop_id: str = "MOUNT_A", abstraction_ref: str = "AUTHENTICATION") -> dict[str, Any]: return property_record(prop_id, "mount", "RULESET_MOUNT", {"abstraction_ref": abstraction_ref, "properties": {}})


def link_property(prop_id: str, ruleset_ref: str, link_type_ref: str, parent_ref: str, child_ref: str) -> dict[str, Any]:
    return property_record(prop_id, "link", ruleset_ref, {"link_type_ref": link_type_ref, "parent_ref": parent_ref, "child_ref": child_ref, "properties": {}})


def canonical_index(entities: list[dict[str, Any]]) -> dict[str, tuple[str, str, dict[str, Any]]]:
    result: dict[str, tuple[str, str, dict[str, Any]]] = {}
    for entity in entities:
        entity_id = entity["id"]
        if entity_id in result: raise AssertionError(f"duplicate canonical identity in test oracle: {entity_id}")
        result[entity_id] = ("entity", entity_id, entity)
        for prop in entity.get("properties", []):
            prop_id = prop["id"]
            if prop_id in result: raise AssertionError(f"duplicate canonical identity in test oracle: {prop_id}")
            result[prop_id] = ("property", entity_id, prop)
    return result


def owner_for_ref(entities: list[dict[str, Any]], ref: str) -> str | None:
    item = canonical_index(entities).get(ref)
    return item[1] if item else None


def projected_event_refs(entity: dict[str, Any]) -> list[str]:
    return [prop["id"] for prop in entity.get("properties", []) if prop.get("property_type_ref") == "event"]


def projected_props_refs(entity: dict[str, Any]) -> list[str]:
    return [prop["id"] for prop in entity.get("properties", []) if prop.get("property_type_ref") in CW_SCENE_PROPERTY_TYPES]


def generic_projection_groups(entities: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    groups: set[tuple[str, str, str]] = set()
    index = canonical_index(entities)
    for entity in entities:
        for prop in entity.get("properties", []):
            if prop.get("property_type_ref") != "link": continue
            value = prop.get("value", {})
            link_type = value.get("link_type_ref")
            if link_type not in CW_GENERIC_LINK_TYPES: continue
            parent = index.get(value.get("parent_ref")); child = index.get(value.get("child_ref"))
            if parent and child: groups.add((parent[1], child[1], link_type))
    return groups
