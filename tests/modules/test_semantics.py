from __future__ import annotations

import copy
import unittest

from cw_oracle import (
    CW_LINK_ROLES,
    CW_PROPERTY_TYPES,
    data_property,
    entity_record,
    event_property,
    function_property,
    type_property,
)
from server.semantics import (
    DEFAULT_COLOR_SPACES,
    DEFAULT_RULESETS,
    declared_type,
    validate_color_spaces,
    validate_properties,
    validate_rulesets,
)


class SemanticsTests(unittest.TestCase):
    def _rulesets(self):
        return validate_rulesets(copy.deepcopy(DEFAULT_RULESETS), validate_color_spaces(copy.deepcopy(DEFAULT_COLOR_SPACES)))

    def test_color_space_ids_are_unique(self):
        colors = copy.deepcopy(DEFAULT_COLOR_SPACES)
        colors.append(copy.deepcopy(colors[0]))
        with self.assertRaisesRegex(ValueError, "duplicate color space id"):
            validate_color_spaces(colors)

    def test_color_space_requires_complete_bounded_rgb_triplets(self):
        for bad in ([1, 0], [1, 0, 2], "red"):
            colors = copy.deepcopy(DEFAULT_COLOR_SPACES)
            colors[0]["colors"]["base"] = bad
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    validate_color_spaces(colors)

    def test_link_ruleset_requires_explicit_semantic_roles(self):
        colors = validate_color_spaces(copy.deepcopy(DEFAULT_COLOR_SPACES))
        rulesets = copy.deepcopy(DEFAULT_RULESETS)
        link = next(item for item in rulesets if item["property_type_ref"] == "link")
        del link["semantic_roles"]
        with self.assertRaisesRegex(ValueError, "requires semantic_roles"):
            validate_rulesets(rulesets, colors)

    def test_link_ruleset_roles_match_cw_contract(self):
        rulesets = self._rulesets()
        for ruleset in rulesets.values():
            if ruleset["property_type_ref"] != "link":
                continue
            expected_parent, expected_child = CW_LINK_ROLES[ruleset["link_type_ref"]]
            self.assertEqual(ruleset["semantic_roles"]["parent_ref"], expected_parent)
            self.assertEqual(ruleset["semantic_roles"]["child_ref"], expected_child)

    def test_unknown_property_type_ruleset_is_rejected(self):
        colors = validate_color_spaces(copy.deepcopy(DEFAULT_COLOR_SPACES))
        rulesets = copy.deepcopy(DEFAULT_RULESETS)
        rulesets.append({"id": "RULESET_UNKNOWN", "name": "Unknown", "property_type_ref": "magic"})
        with self.assertRaisesRegex(ValueError, "unsupported property_type_ref"):
            validate_rulesets(rulesets, colors)

    def test_default_catalog_exactly_covers_cw_property_primitives(self):
        self.assertEqual({item["property_type_ref"] for item in DEFAULT_RULESETS}, CW_PROPERTY_TYPES)

    def test_missing_type_is_unresolved_and_not_inferred(self):
        entity = entity_record("THING", "Looks Like A Service", properties=[event_property()])
        validate_properties([entity], self._rulesets())
        self.assertIsNone(declared_type(entity))

    def test_multiple_type_properties_are_invalid(self):
        entity = entity_record("THING", properties=[type_property("TYPE_1", "a"), type_property("TYPE_2", "b")])
        with self.assertRaisesRegex(ValueError, "multiple Type Properties"):
            validate_properties([entity], self._rulesets())

    def test_declared_property_requires_matching_ruleset(self):
        prop = data_property()
        prop["ruleset_ref"] = "RULESET_EVENT"
        with self.assertRaisesRegex(ValueError, "does not match ruleset"):
            validate_properties([entity_record("OWNER", properties=[prop])], self._rulesets())

    def test_declared_property_requires_value_object(self):
        prop = data_property()
        prop["value"] = None
        with self.assertRaisesRegex(ValueError, "value must be an object"):
            validate_properties([entity_record("OWNER", properties=[prop])], self._rulesets())

    def test_function_refs_resolve_or_fail_loudly(self):
        entity = entity_record("OWNER", properties=[data_property("IN"), function_property("FN", input_refs=["IN"], output_refs=["MISSING"])])
        with self.assertRaisesRegex(ValueError, "must resolve canonical identities"):
            validate_properties([entity], self._rulesets())

    def test_property_metadata_cannot_rebind_canonical_owner(self):
        prop = data_property()
        prop["metadata"] = {"workspace_entity_ref": "OTHER"}
        with self.assertRaisesRegex(ValueError, "must equal canonical owner"):
            validate_properties([entity_record("OWNER", properties=[prop])], self._rulesets())

    def test_existing_property_may_be_incomplete_only_by_absence_not_by_malformed_claim(self):
        # No Data Property at all is unresolved/incomplete and valid.
        validate_properties([entity_record("OWNER")], self._rulesets())
        # Once Data is explicitly declared it must carry its discriminator.
        prop = data_property()
        del prop["value"]["data_type_ref"]
        with self.assertRaisesRegex(ValueError, "requires data_type_ref"):
            validate_properties([entity_record("OWNER", properties=[prop])], self._rulesets())


if __name__ == "__main__":
    unittest.main()
