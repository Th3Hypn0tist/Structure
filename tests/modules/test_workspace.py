from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from server.workspace import DEFAULT_WORKSPACE, WorkspaceStore


class WorkspaceTests(unittest.TestCase):
    def test_default_workspace_camera_contract(self):
        camera = DEFAULT_WORKSPACE["settings"]["camera_defaults"]
        self.assertEqual(camera["fov"], 60.0)
        self.assertEqual(camera["wheel_zoom_speed"], 0.15)
        self.assertEqual(camera["drag_pan_speed"], 0.01)
        self.assertEqual(camera["near_clip"], 0.05)
        self.assertEqual(camera["far_clip"], 1000.0)

    def test_workspace_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkspaceStore(str(Path(directory) / "workspace.json"))
            workspace = copy.deepcopy(DEFAULT_WORKSPACE)
            workspace["entities"].append(
                {
                    "id": "ENTITY_A",
                    "name": "A",
                    "entity_type_ref": "entity",
                    "status": "unlocked",
                    "position": [1, 2, 3],
                    "properties": [],
                }
            )

            saved = store.save(workspace)
            loaded = store.load()

            self.assertEqual(saved, loaded)
            self.assertEqual(loaded["entities"][0]["position"], [1.0, 2.0, 3.0])

    def test_workspace_rejects_fov_outside_contract(self):
        for fov in (14.99, 170.01):
            with self.subTest(fov=fov), tempfile.TemporaryDirectory() as directory:
                store = WorkspaceStore(str(Path(directory) / "workspace.json"))
                workspace = copy.deepcopy(DEFAULT_WORKSPACE)
                workspace["camera"]["fov"] = fov

                with self.assertRaisesRegex(ValueError, "15..170"):
                    store.save(workspace)

    def test_workspace_accepts_link_and_event_properties(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkspaceStore(str(Path(directory) / "workspace.json"))
            workspace = copy.deepcopy(DEFAULT_WORKSPACE)
            workspace["entities"] = [
                {
                    "id": "PARENT",
                    "position": [0, 0, 0],
                    "properties": [],
                },
                {
                    "id": "CHILD",
                    "position": [1, 0, 0],
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
                        },
                        {
                            "id": "EVENT_0001",
                            "property_type_ref": "event",
                            "ruleset_ref": "RULESET_EVENT",
                            "value": {"event_type_ref": "changed", "properties": {}},
                        },
                    ],
                },
            ]

            validated = store.save(workspace)
            self.assertEqual(len(validated["entities"][1]["properties"]), 2)


if __name__ == "__main__":
    unittest.main()
