from __future__ import annotations

import copy

import pytest

from server.semantics import DEFAULT_COLOR_SPACES, DEFAULT_RULESETS, validate_color_spaces, validate_properties, validate_rulesets


def _indexes():
    color_spaces = copy.deepcopy(DEFAULT_COLOR_SPACES)
    rulesets = copy.deepcopy(DEFAULT_RULESETS)
    color_index = validate_color_spaces(color_spaces)
    ruleset_index = validate_rulesets(rulesets, color_index)
    return ruleset_index


def test_link_property_validates_against_ruleset_and_endpoints():
    entities = [
        {"id": "PARENT", "properties": []},
        {
            "id": "CHILD",
            "properties": [
                {
                    "id": "LINK_0001",
                    "property_type_ref": "link",
                    "ruleset_ref": "RULESET_LINK_DEPENDENCY",
                    "value": {
                        "link_type_ref": "dependency",
                        "parent_ref": "PARENT",
                        "child_ref": "CHILD",
                        "properties": {},
                    },
                }
            ],
        },
    ]

    validate_properties(entities, _indexes())
    prop = entities[1]["properties"][0]
    assert prop["status"] == "unlocked"
    assert prop["metadata"]["workspace_entity_ref"] == "CHILD"


def test_link_property_rejects_unresolved_endpoint():
    entities = [
        {
            "id": "CHILD",
            "properties": [
                {
                    "id": "LINK_0001",
                    "property_type_ref": "link",
                    "ruleset_ref": "RULESET_LINK_DEPENDENCY",
                    "value": {
                        "link_type_ref": "dependency",
                        "parent_ref": "MISSING",
                        "child_ref": "CHILD",
                        "properties": {},
                    },
                }
            ],
        }
    ]

    with pytest.raises(ValueError, match="parent_ref does not resolve"):
        validate_properties(entities, _indexes())


def test_event_property_validates_with_event_ruleset():
    entities = [
        {
            "id": "ENTITY_A",
            "properties": [
                {
                    "id": "EVENT_0001",
                    "property_type_ref": "event",
                    "ruleset_ref": "RULESET_EVENT",
                    "value": {"event_type_ref": "changed", "properties": {}},
                }
            ],
        }
    ]

    validate_properties(entities, _indexes())
    prop = entities[0]["properties"][0]
    assert prop["metadata"]["workspace_entity_ref"] == "ENTITY_A"


def test_entity_property_identity_collision_is_rejected():
    entities = [
        {"id": "ENTITY_A", "properties": []},
        {
            "id": "ENTITY_B",
            "properties": [
                {
                    "id": "ENTITY_A",
                    "property_type_ref": "event",
                    "ruleset_ref": "RULESET_EVENT",
                    "value": {"event_type_ref": "changed", "properties": {}},
                }
            ],
        },
    ]

    with pytest.raises(ValueError, match="canonical identity collision"):
        validate_properties(entities, _indexes())
