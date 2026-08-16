from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from server.workspace import DEFAULT_WORKSPACE, WORKSPACE_VERSION, WorkspaceStore


class WorkspaceTests(unittest.TestCase):
    def test_workspace_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkspaceStore(str(Path(directory) / "workspace.json"))
            workspace = copy.deepcopy(DEFAULT_WORKSPACE)
            workspace["entities"].append({"id": "ENTITY_A", "name": "A", "position": [1, 2, 3], "properties": []})
            saved = store.save(workspace)
            self.assertEqual(saved, store.load())

    def test_only_name_is_required_semantic_authoring_fact(self):
        workspace = copy.deepcopy(DEFAULT_WORKSPACE)
        workspace["entities"] = [{"id": "ENTITY_A", "name": "A", "position": [0, 0, 0], "properties": []}]
        WorkspaceStore("unused")._validate(workspace)

    def test_legacy_entity_type_field_fails_loudly(self):
        workspace = copy.deepcopy(DEFAULT_WORKSPACE)
        workspace["entities"] = [{"id": "ENTITY_A", "name": "A", "entity_type_ref": "service", "position": [0, 0, 0], "properties": []}]
        with self.assertRaisesRegex(ValueError, "removed legacy field entity_type_ref"):
            WorkspaceStore("unused")._validate(workspace)

    def test_old_workspace_version_is_not_migrated(self):
        workspace = copy.deepcopy(DEFAULT_WORKSPACE)
        workspace["version"] = "0.2.0"
        with self.assertRaisesRegex(ValueError, f"exactly {WORKSPACE_VERSION}"):
            WorkspaceStore("unused")._validate(workspace)

    def test_removed_top_level_view_fails_loudly(self):
        workspace = copy.deepcopy(DEFAULT_WORKSPACE)
        workspace["view"] = {"ruleset_ref": "ALL"}
        with self.assertRaisesRegex(ValueError, "workspace.view is removed"):
            WorkspaceStore("unused")._validate(workspace)

    def test_missing_workspace_file_is_not_replaced_by_starter(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkspaceStore(str(Path(directory) / "workspace.json"))
            with self.assertRaises(FileNotFoundError):
                store.load()

    def test_missing_settings_do_not_receive_fallbacks(self):
        workspace = copy.deepcopy(DEFAULT_WORKSPACE)
        del workspace["settings"]["view_defaults"]
        with self.assertRaisesRegex(ValueError, "settings.view_defaults"):
            WorkspaceStore("unused")._validate(workspace)

    def test_active_ruleset_must_resolve(self):
        workspace = copy.deepcopy(DEFAULT_WORKSPACE)
        workspace["settings"]["view_defaults"]["ruleset_ref"] = "MISSING"
        with self.assertRaisesRegex(ValueError, "ruleset_ref does not resolve"):
            WorkspaceStore("unused")._validate(workspace)


if __name__ == "__main__":
    unittest.main()
