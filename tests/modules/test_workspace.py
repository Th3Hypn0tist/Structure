from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from cw_oracle import data_property, entity_record, event_property, type_property, workspace_fixture
from server.workspace import DEFAULT_WORKSPACE, WORKSPACE_VERSION, WorkspaceStore


class WorkspaceTests(unittest.TestCase):
    def validate(self, workspace):
        return WorkspaceStore("unused")._validate(workspace)

    def test_name_only_entity_is_valid_incomplete_structure(self):
        workspace = workspace_fixture()
        workspace["entities"] = [entity_record("ENTITY_A", "A")]
        self.validate(workspace)

    def test_missing_required_structural_container_is_invalid_not_incomplete(self):
        workspace = workspace_fixture()
        del workspace["entities"]
        with self.assertRaisesRegex(ValueError, "workspace.entities"):
            self.validate(workspace)

    def test_workspace_round_trip_is_source_preserving(self):
        workspace = workspace_fixture()
        workspace["entities"] = [entity_record("A", properties=[type_property(), data_property(), event_property()])]
        original = copy.deepcopy(workspace)
        with tempfile.TemporaryDirectory() as directory:
            store = WorkspaceStore(str(Path(directory) / "workspace.json"))
            saved = store.save(workspace)
            loaded = store.load()
        self.assertEqual(saved, original)
        self.assertEqual(loaded, original)

    def test_save_validation_does_not_infer_or_enrich_semantics(self):
        workspace = workspace_fixture()
        workspace["entities"] = [entity_record("ORDER_SERVICE", "Order Service")]
        original = copy.deepcopy(workspace)
        validated = self.validate(workspace)
        self.assertEqual(validated, original)
        self.assertEqual(validated["entities"][0]["properties"], [])

    def test_legacy_entity_type_field_fails_loudly(self):
        workspace = workspace_fixture()
        workspace["entities"] = [entity_record("A")]
        workspace["entities"][0]["entity_type_ref"] = "service"
        with self.assertRaisesRegex(ValueError, "removed legacy field entity_type_ref"):
            self.validate(workspace)

    def test_old_workspace_version_is_not_silently_migrated(self):
        workspace = workspace_fixture()
        workspace["version"] = "0.2.0"
        with self.assertRaisesRegex(ValueError, f"exactly {WORKSPACE_VERSION}"):
            self.validate(workspace)

    def test_removed_parallel_view_root_fails_loudly(self):
        workspace = workspace_fixture()
        workspace["view"] = {"ruleset_ref": "ALL"}
        with self.assertRaisesRegex(ValueError, "workspace.view is removed"):
            self.validate(workspace)

    def test_missing_settings_are_not_backfilled_by_compatibility_layer(self):
        workspace = workspace_fixture()
        del workspace["settings"]["view_defaults"]
        with self.assertRaisesRegex(ValueError, "settings.view_defaults"):
            self.validate(workspace)

    def test_active_projection_ruleset_must_resolve(self):
        workspace = workspace_fixture()
        workspace["settings"]["view_defaults"]["ruleset_ref"] = "MISSING"
        with self.assertRaisesRegex(ValueError, "ruleset_ref does not resolve"):
            self.validate(workspace)

    def test_switching_projection_ruleset_does_not_change_canonical_entities(self):
        workspace = workspace_fixture()
        workspace["entities"] = [entity_record("A", properties=[data_property()])]
        canonical = copy.deepcopy(workspace["entities"])
        dependency = next(item["id"] for item in workspace["rulesets"] if item.get("link_type_ref") == "dependency")
        workspace["settings"]["view_defaults"]["ruleset_ref"] = dependency
        self.validate(workspace)
        self.assertEqual(workspace["entities"], canonical)

    def test_projection_orientation_is_not_canonical_semantic_input(self):
        view = DEFAULT_WORKSPACE["settings"]["view_defaults"]
        self.assertNotIn("property_panel_direction", view)

    def test_human_machine_contract_sync_requires_same_human_revision(self):
        workspace = workspace_fixture()
        entity = entity_record("A")
        entity["contract"] = {
            "human": "A does X.",
            "human_revision": 2,
            "machine": {
                "status": "synchronized",
                "generated_from_human_revision": 1,
                "data": {},
            },
        }
        workspace["entities"] = [entity]
        with self.assertRaisesRegex(ValueError, "must match current human revision"):
            self.validate(workspace)

    def test_synchronized_machine_contract_may_match_current_human_revision(self):
        workspace = workspace_fixture()
        entity = entity_record("A")
        entity["contract"] = {
            "human": "A does X.",
            "human_revision": 2,
            "machine": {
                "status": "synchronized",
                "generated_from_human_revision": 2,
                "data": {"contract": "derived"},
            },
        }
        workspace["entities"] = [entity]
        self.validate(workspace)

    def test_missing_workspace_file_is_never_replaced_with_starter_truth(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkspaceStore(str(Path(directory) / "workspace.json"))
            with self.assertRaises(FileNotFoundError):
                store.load()


if __name__ == "__main__":
    unittest.main()
