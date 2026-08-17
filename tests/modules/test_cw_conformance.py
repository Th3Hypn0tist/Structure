from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from cw_oracle import (
    CW_CAUSAL_LINK_TYPES,
    CW_EFFECT_FORBIDDEN_DIRECTED_FIELDS,
    CW_EVENT_FORBIDDEN_DIRECTED_FIELDS,
    CW_GENERIC_LINK_TYPES,
    CW_LINK_FORBIDDEN_DUPLICATE_FIELDS,
    CW_LINK_ROLES,
    CW_LINK_TYPES,
    CW_PROPERTY_TYPES,
    CW_SEMANTIC_EXPORT_KEYS,
    CW_VALUE_TYPE_FIELDS,
    CW_VIEW_RUNTIME_KEYS,
    canonical_index,
    data_property,
    effect_property,
    entity_record,
    event_property,
    function_property,
    generic_projection_groups,
    link_property,
    mount_property,
    projected_event_refs,
    projected_props_refs,
    type_property,
    workspace_fixture,
)
from server.abstractions import ABSTRACTION_VERSION, AbstractionLibrary
from server.semantics import (
    DEFAULT_COLOR_SPACES,
    DEFAULT_RULESETS,
    declared_type,
    validate_color_spaces,
    validate_properties,
    validate_rulesets,
)
from server.workspace import WorkspaceStore


class CWConformanceTests(unittest.TestCase):
    def rulesets(self):
        colors = validate_color_spaces(copy.deepcopy(DEFAULT_COLOR_SPACES))
        return validate_rulesets(copy.deepcopy(DEFAULT_RULESETS), colors)

    def validate_entities(self, entities):
        validate_properties(entities, self.rulesets())

    def test_cw_ruleset_catalog_covers_every_locked_property_primitive(self):
        property_types = {ruleset["property_type_ref"] for ruleset in DEFAULT_RULESETS}
        self.assertEqual(property_types, CW_PROPERTY_TYPES)

    def test_cw_link_catalog_covers_every_locked_link_semantic(self):
        link_rulesets = [ruleset for ruleset in DEFAULT_RULESETS if ruleset["property_type_ref"] == "link"]
        self.assertEqual({ruleset["link_type_ref"] for ruleset in link_rulesets}, CW_LINK_TYPES)
        for ruleset in link_rulesets:
            expected = CW_LINK_ROLES[ruleset["link_type_ref"]]
            actual = (ruleset["semantic_roles"]["parent_ref"], ruleset["semantic_roles"]["child_ref"])
            self.assertEqual(actual, expected, ruleset["link_type_ref"])
            self.assertEqual(ruleset["property_owner"], "ruleset_defined")

    def test_every_non_link_property_has_explicit_type_discriminator(self):
        properties = [
            type_property(),
            mount_property(),
            event_property(),
            effect_property(),
            data_property(),
            function_property(),
        ]
        entity = entity_record("OWNER", properties=properties)
        self.validate_entities([entity])
        for prop in properties:
            field = CW_VALUE_TYPE_FIELDS[prop["property_type_ref"]]
            self.assertIsInstance(prop["value"].get(field), str)
            self.assertTrue(prop["value"][field])

    def test_unresolved_type_is_incomplete_not_invalid_and_is_never_inferred(self):
        entity = entity_record("LOOKS_LIKE_SERVICE", "Order Service", properties=[event_property()])
        self.validate_entities([entity])
        self.assertIsNone(declared_type(entity))

    def test_explicit_type_is_a_property_not_entity_shape(self):
        entity = entity_record("SERVICE", properties=[type_property(type_ref="service")])
        self.validate_entities([entity])
        self.assertEqual(declared_type(entity), "service")
        self.assertNotIn("entity_type_ref", entity)

    def test_canonical_identity_namespace_is_shared_by_entities_and_properties(self):
        entity = entity_record("SAME", properties=[data_property("SAME")])
        with self.assertRaisesRegex(ValueError, "canonical identity collision"):
            self.validate_entities([entity])

    def test_property_identity_must_be_globally_unique(self):
        entities = [
            entity_record("A", properties=[data_property("DATA_SHARED")]),
            entity_record("B", properties=[data_property("DATA_SHARED")]),
        ]
        with self.assertRaisesRegex(ValueError, "canonical identity collision"):
            self.validate_entities(entities)

    def test_ruleset_ref_is_authoritative_and_must_match_property_type(self):
        prop = data_property()
        prop["ruleset_ref"] = "RULESET_EVENT"
        with self.assertRaisesRegex(ValueError, "does not match ruleset"):
            self.validate_entities([entity_record("OWNER", properties=[prop])])

    def test_link_endpoints_must_resolve_to_canonical_identity(self):
        entity = entity_record(
            "OWNER",
            properties=[link_property("LINK", "RULESET_LINK_DEPENDENCY", "dependency", "MISSING", "OWNER")],
        )
        with self.assertRaisesRegex(ValueError, "parent_ref does not resolve"):
            self.validate_entities([entity])

    def test_link_type_must_match_ruleset(self):
        entities = [
            entity_record("A"),
            entity_record("B", properties=[link_property("LINK", "RULESET_LINK_DEPENDENCY", "ownership", "A", "B")]),
        ]
        with self.assertRaisesRegex(ValueError, "link_type_ref does not match ruleset"):
            self.validate_entities(entities)

    def test_directed_semantics_have_one_authoritative_representation(self):
        event = event_property()
        for field in CW_EVENT_FORBIDDEN_DIRECTED_FIELDS:
            mutated = copy.deepcopy(event)
            mutated["value"][field] = ["X"]
            with self.subTest(event_field=field):
                with self.assertRaisesRegex(ValueError, "embeds authoritative directed reference"):
                    self.validate_entities([entity_record("OWNER", properties=[mutated])])

        effect = effect_property()
        for field in CW_EFFECT_FORBIDDEN_DIRECTED_FIELDS:
            mutated = copy.deepcopy(effect)
            mutated["value"][field] = "X" if field == "target_ref" else ["X"]
            with self.subTest(effect_field=field):
                with self.assertRaisesRegex(ValueError, "embeds authoritative target reference"):
                    self.validate_entities([entity_record("OWNER", properties=[mutated])])

        entities = [entity_record("A"), entity_record("B")]
        link = link_property("LINK", "RULESET_LINK_DEPENDENCY", "dependency", "A", "B")
        for field in CW_LINK_FORBIDDEN_DUPLICATE_FIELDS:
            mutated = copy.deepcopy(link)
            mutated["value"][field] = "duplicate"
            with self.subTest(link_field=field):
                with self.assertRaisesRegex(ValueError, "duplicates canonical endpoint semantics"):
                    self.validate_entities([entities[0], entity_record("B", properties=[mutated])])

    def test_event_effect_and_effect_target_directions_are_enforced(self):
        event = event_property("EVENT")
        effect = effect_property("EFFECT")
        target = data_property("TARGET")
        valid = entity_record(
            "OWNER",
            properties=[
                event,
                effect,
                target,
                link_property("EE", "RULESET_LINK_EVENT_EFFECT", "event_effect", "EVENT", "EFFECT"),
                link_property("ET", "RULESET_LINK_EFFECT_TARGET", "effect_target", "EFFECT", "TARGET"),
            ],
        )
        self.validate_entities([valid])

        wrong_event_effect = copy.deepcopy(valid)
        next(prop for prop in wrong_event_effect["properties"] if prop["id"] == "EE")["value"].update(
            parent_ref="EFFECT", child_ref="EVENT"
        )
        with self.assertRaisesRegex(ValueError, "Event -> Effect"):
            self.validate_entities([wrong_event_effect])

        wrong_effect_target = copy.deepcopy(valid)
        next(prop for prop in wrong_effect_target["properties"] if prop["id"] == "ET")["value"]["parent_ref"] = "EVENT"
        with self.assertRaisesRegex(ValueError, "parent_ref must be Effect"):
            self.validate_entities([wrong_effect_target])

    def test_all_event_input_family_links_target_an_event(self):
        for link_type in ("event_read", "event_input", "event_cause", "event_condition"):
            ruleset = next(item for item in DEFAULT_RULESETS if item.get("link_type_ref") == link_type)
            entities = [
                entity_record("SOURCE", properties=[data_property("SOURCE_DATA")]),
                entity_record("TARGET", properties=[data_property("NOT_EVENT")]),
            ]
            entities[0]["properties"].append(
                link_property(f"LINK_{link_type}", ruleset["id"], link_type, "SOURCE_DATA", "NOT_EVENT")
            )
            with self.subTest(link_type=link_type):
                with self.assertRaisesRegex(ValueError, "child_ref must be Event"):
                    self.validate_entities(entities)

    def test_event_output_origin_is_event(self):
        entities = [
            entity_record("A", properties=[data_property("NOT_EVENT")]),
            entity_record("B", properties=[data_property("TARGET")]),
        ]
        entities[0]["properties"].append(
            link_property("OUT", "RULESET_LINK_EVENT_OUTPUT", "event_output", "NOT_EVENT", "TARGET")
        )
        with self.assertRaisesRegex(ValueError, "parent_ref must be Event"):
            self.validate_entities(entities)

    def test_function_io_refs_are_canonical_refs_not_embedded_copies(self):
        function = function_property("FUNCTION", input_refs=["DATA_IN"], output_refs=["DATA_OUT"])
        entity = entity_record(
            "OWNER",
            properties=[data_property("DATA_IN"), data_property("DATA_OUT"), function],
        )
        self.validate_entities([entity])
        broken = copy.deepcopy(entity)
        next(prop for prop in broken["properties"] if prop["id"] == "FUNCTION")["value"]["input_refs"] = ["MISSING"]
        with self.assertRaisesRegex(ValueError, "must resolve canonical identities"):
            self.validate_entities([broken])

    def test_mount_is_reference_composition_not_source_copy(self):
        mount = mount_property()
        self.validate_entities([entity_record("MOUNT_OWNER", properties=[mount])])
        self.assertEqual(set(mount["value"]), {"abstraction_ref", "properties"})
        self.assertNotIn("entities", mount["value"])

    def test_projection_can_aggregate_visual_links_without_collapsing_canonical_contracts(self):
        entities = [
            entity_record("A", properties=[data_property("A1"), data_property("A2")]),
            entity_record("B", properties=[data_property("B1"), data_property("B2")]),
        ]
        entities[0]["properties"].extend([
            link_property("L1", "RULESET_LINK_DEPENDENCY", "dependency", "B1", "A1"),
            link_property("L2", "RULESET_LINK_DEPENDENCY", "dependency", "B2", "A2"),
        ])
        self.validate_entities(entities)
        canonical_links = [
            prop
            for entity in entities
            for prop in entity["properties"]
            if prop["property_type_ref"] == "link"
        ]
        self.assertEqual(len(canonical_links), 2)
        self.assertEqual(generic_projection_groups(entities), {("B", "A", "dependency")})
        self.assertEqual(len(canonical_links), 2, "projection must not rewrite canonical Link count")

    def test_event_and_props_projection_are_derived_from_property_types_only(self):
        entity = entity_record(
            "OWNER",
            properties=[
                event_property("EVENT_1"),
                event_property("EVENT_2"),
                effect_property("EFFECT"),
                data_property("DATA"),
                function_property("FUNCTION"),
                type_property("TYPE"),
                mount_property("MOUNT"),
            ],
        )
        self.assertEqual(projected_event_refs(entity), ["EVENT_1", "EVENT_2"])
        self.assertEqual(projected_props_refs(entity), ["EFFECT", "DATA", "FUNCTION", "TYPE", "MOUNT"])

    def test_workspace_round_trip_preserves_canonical_semantics_exactly(self):
        workspace = workspace_fixture()
        workspace["entities"] = [
            entity_record(
                "OWNER",
                properties=[type_property(), data_property(), event_property(), effect_property()],
            )
        ]
        with tempfile.TemporaryDirectory() as directory:
            store = WorkspaceStore(str(Path(directory) / "workspace.json"))
            original = copy.deepcopy(workspace)
            store.save(workspace)
            loaded = store.load()
            self.assertEqual(loaded, original)
            self.assertEqual(canonical_index(loaded["entities"]), canonical_index(original["entities"]))

    def test_abstraction_round_trip_preserves_semantic_source_exactly(self):
        workspace = workspace_fixture()
        workspace["entities"] = [entity_record("OWNER", properties=[type_property(), data_property()])]
        abstraction = {
            "version": ABSTRACTION_VERSION,
            "id": "CW_TEST",
            "name": "CW test",
            "entities": copy.deepcopy(workspace["entities"]),
            "rulesets": copy.deepcopy(workspace["rulesets"]),
            "color_spaces": copy.deepcopy(workspace["color_spaces"]),
        }
        with tempfile.TemporaryDirectory() as directory:
            library = AbstractionLibrary(str(Path(directory) / "library"))
            library.publish(copy.deepcopy(abstraction))
            self.assertEqual(library.get("CW_TEST"), abstraction)

    def test_semantic_export_boundary_excludes_view_and_runtime_authority(self):
        workspace = workspace_fixture()
        document = {
            "version": workspace["version"],
            "entities": copy.deepcopy(workspace["entities"]),
            "rulesets": copy.deepcopy(workspace["rulesets"]),
            "color_spaces": copy.deepcopy(workspace["color_spaces"]),
        }
        self.assertEqual(set(document), CW_SEMANTIC_EXPORT_KEYS)
        self.assertTrue(set(document).isdisjoint(CW_VIEW_RUNTIME_KEYS))
        json.dumps(document)

    def test_ruleset_color_spaces_are_resolvable_and_bounded(self):
        colors = validate_color_spaces(copy.deepcopy(DEFAULT_COLOR_SPACES))
        rulesets = validate_rulesets(copy.deepcopy(DEFAULT_RULESETS), colors)
        for ruleset in rulesets.values():
            if ruleset["property_type_ref"] != "link":
                continue
            self.assertIn(ruleset["color_space_ref"], colors)
            color_space = colors[ruleset["color_space_ref"]]
            for variant in ("base", "flow", "selected"):
                self.assertEqual(len(color_space["colors"][variant]), 3)
                self.assertTrue(all(0 <= component <= 1 for component in color_space["colors"][variant]))

    def test_oracle_partition_covers_all_links_without_overlap(self):
        self.assertTrue(CW_CAUSAL_LINK_TYPES.isdisjoint(CW_GENERIC_LINK_TYPES))
        self.assertEqual(CW_CAUSAL_LINK_TYPES | CW_GENERIC_LINK_TYPES, CW_LINK_TYPES)


if __name__ == "__main__":
    unittest.main()
