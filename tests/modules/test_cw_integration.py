from __future__ import annotations

import copy
import unittest

from cw_oracle import CW_CAUSAL_LINK_TYPES, CW_GENERIC_LINK_TYPES, CW_PROPERTY_TYPES, canonical_index
from server.starting_scene import starting_entities
from server.workspace import WorkspaceStore, starting_workspace


class CWIntegrationTests(unittest.TestCase):
    def test_starting_scene_is_a_valid_complete_canonical_fixture(self):
        workspace = starting_workspace()
        validated = WorkspaceStore("unused")._validate(copy.deepcopy(workspace))
        self.assertEqual(validated, workspace)

    def test_starting_scene_has_global_canonical_identity_integrity(self):
        entities = starting_entities()
        index = canonical_index(entities)
        expected_count = len(entities) + sum(len(entity["properties"]) for entity in entities)
        self.assertEqual(len(index), expected_count)

    def test_starting_scene_references_resolve_without_projection_help(self):
        entities = starting_entities()
        index = canonical_index(entities)
        for entity in entities:
            for prop in entity["properties"]:
                if prop["property_type_ref"] == "link":
                    with self.subTest(link=prop["id"]):
                        self.assertIn(prop["value"]["parent_ref"], index)
                        self.assertIn(prop["value"]["child_ref"], index)
                if prop["property_type_ref"] == "function":
                    for field in ("input_refs", "output_refs"):
                        for ref in prop["value"].get(field, []):
                            with self.subTest(function=prop["id"], field=field, ref=ref):
                                self.assertIn(ref, index)

    def test_starting_scene_uses_only_cw_property_primitives(self):
        actual = {
            prop["property_type_ref"]
            for entity in starting_entities()
            for prop in entity["properties"]
        }
        self.assertTrue(actual <= CW_PROPERTY_TYPES)
        self.assertTrue({"type", "link", "event", "effect", "data", "function"} <= actual)

    def test_starting_scene_links_partition_into_known_cw_semantics(self):
        link_types = {
            prop["value"]["link_type_ref"]
            for entity in starting_entities()
            for prop in entity["properties"]
            if prop["property_type_ref"] == "link"
        }
        self.assertTrue(link_types <= CW_CAUSAL_LINK_TYPES | CW_GENERIC_LINK_TYPES)
        self.assertTrue(link_types & CW_CAUSAL_LINK_TYPES)
        self.assertTrue(link_types & CW_GENERIC_LINK_TYPES)

    def test_validating_starting_scene_does_not_mutate_semantic_source(self):
        workspace = starting_workspace()
        source = copy.deepcopy(workspace)
        WorkspaceStore("unused")._validate(workspace)
        self.assertEqual(workspace["entities"], source["entities"])
        self.assertEqual(workspace["rulesets"], source["rulesets"])
        self.assertEqual(workspace["color_spaces"], source["color_spaces"])


if __name__ == "__main__":
    unittest.main()
