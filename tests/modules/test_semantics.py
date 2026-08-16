from __future__ import annotations

import copy
import unittest

from server.semantics import DEFAULT_COLOR_SPACES, DEFAULT_RULESETS, declared_type, validate_color_spaces, validate_properties, validate_rulesets


class SemanticsTests(unittest.TestCase):
    def _rulesets(self):
        colors = copy.deepcopy(DEFAULT_COLOR_SPACES)
        rulesets = copy.deepcopy(DEFAULT_RULESETS)
        return validate_rulesets(rulesets, validate_color_spaces(colors))

    def test_type_is_explicit_property(self):
        entity = {
            "id": "SERVICE_A",
            "name": "Service A",
            "position": [0, 0, 0],
            "properties": [{"id": "TYPE_0001", "property_type_ref": "type", "ruleset_ref": "RULESET_TYPE", "value": {"type_ref": "service", "properties": {}}}],
        }
        validate_properties([entity], self._rulesets())
        self.assertEqual(declared_type(entity), "service")

    def test_missing_type_is_allowed_and_not_inferred(self):
        entity = {
            "id": "THING",
            "name": "Looks Like A Service",
            "position": [0, 0, 0],
            "properties": [{"id": "EVENT_0001", "property_type_ref": "event", "ruleset_ref": "RULESET_EVENT", "value": {"event_type_ref": "changed", "properties": {}}}],
        }
        validate_properties([entity], self._rulesets())
        self.assertIsNone(declared_type(entity))

    def test_multiple_type_properties_are_rejected(self):
        entity = {
            "id": "THING",
            "name": "Thing",
            "position": [0, 0, 0],
            "properties": [
                {"id": "TYPE_1", "property_type_ref": "type", "ruleset_ref": "RULESET_TYPE", "value": {"type_ref": "a", "properties": {}}},
                {"id": "TYPE_2", "property_type_ref": "type", "ruleset_ref": "RULESET_TYPE", "value": {"type_ref": "b", "properties": {}}},
            ],
        }
        with self.assertRaisesRegex(ValueError, "multiple Type Properties"):
            validate_properties([entity], self._rulesets())

    def test_mount_is_reference_property_not_copy(self):
        entity = {
            "id": "MOUNTED",
            "name": "Authentication",
            "position": [0, 0, 0],
            "properties": [{"id": "MOUNT_1", "property_type_ref": "mount", "ruleset_ref": "RULESET_MOUNT", "value": {"abstraction_ref": "AUTHENTICATION", "properties": {}}}],
        }
        validate_properties([entity], self._rulesets())
        self.assertNotIn("entities", entity["properties"][0]["value"])

    def test_event_effect_direction_is_enforced(self):
        entities = [{
            "id": "OWNER",
            "name": "Owner",
            "position": [0, 0, 0],
            "properties": [
                {"id": "EVENT", "property_type_ref": "event", "ruleset_ref": "RULESET_EVENT", "value": {"event_type_ref": "go", "properties": {}}},
                {"id": "EFFECT", "property_type_ref": "effect", "ruleset_ref": "RULESET_EFFECT", "value": {"effect_type_ref": "set", "properties": {}}},
                {"id": "LINK", "property_type_ref": "link", "ruleset_ref": "RULESET_LINK_EVENT_EFFECT", "value": {"link_type_ref": "event_effect", "parent_ref": "EFFECT", "child_ref": "EVENT", "properties": {}}},
            ],
        }]
        with self.assertRaisesRegex(ValueError, "Event -> Effect"):
            validate_properties(entities, self._rulesets())

    def test_event_cannot_embed_authoritative_effects(self):
        entity = {
            "id": "OWNER",
            "name": "Owner",
            "position": [0, 0, 0],
            "properties": [{"id": "EVENT", "property_type_ref": "event", "ruleset_ref": "RULESET_EVENT", "value": {"event_type_ref": "go", "effects": ["EFFECT"], "properties": {}}}],
        }
        with self.assertRaisesRegex(ValueError, "embeds authoritative directed reference"):
            validate_properties([entity], self._rulesets())


if __name__ == "__main__":
    unittest.main()
