from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from cw_oracle import entity_record, type_property
from server.spatial import canonical_spatial_position, validate_spatial_entities
from server.workspace import WorkspaceStore, workspace_fixture if False else None
from server.workspace import starting_workspace


class SpatialContractTests(unittest.TestCase):
    def test_coordinate_space_ref_resolves_to_entity_and_preserves_xyz(self):
        space = entity_record("SPACE_SITE", "Site space", position=[0.0, 0.0, 0.0])
        node = entity_record("NODE_A", "Node A", position=[12.5, -3.0, 8.25])
        node["coordinate_space_ref"] = "SPACE_SITE"
        validate_spatial_entities([space, node])
        self.assertEqual(
            canonical_spatial_position(node),
            {
                "position": {"x": 12.5, "y": -3.0, "z": 8.25},
                "coordinate_space_ref": "SPACE_SITE",
            },
        )

    def test_coordinate_space_ref_must_resolve_to_entity_not_property(self):
        space = entity_record("SPACE_SITE", "Site space", properties=[type_property("TYPE_SPACE")])
        node = entity_record("NODE_A", "Node A")
        node["coordinate_space_ref"] = "TYPE_SPACE"
        with self.assertRaisesRegex(ValueError, "does not resolve to Entity"):
            validate_spatial_entities([space, node])

    def test_coordinate_space_ref_rejects_self_reference_and_cycles(self):
        self_ref = entity_record("SPACE_A", "Space A")
        self_ref["coordinate_space_ref"] = "SPACE_A"
        with self.assertRaisesRegex(ValueError, "cannot reference itself"):
            validate_spatial_entities([self_ref])

        a = entity_record("SPACE_A", "Space A")
        b = entity_record("SPACE_B", "Space B")
        c = entity_record("SPACE_C", "Space C")
        a["coordinate_space_ref"] = "SPACE_B"
        b["coordinate_space_ref"] = "SPACE_C"
        c["coordinate_space_ref"] = "SPACE_A"
        with self.assertRaisesRegex(ValueError, "coordinate space cycle"):
            validate_spatial_entities([a, b, c])

    def test_recursive_coordinate_spaces_support_nested_site_building_abstraction(self):
        world = entity_record("SPACE_WORLD", "World")
        site = entity_record("SPACE_SITE", "Site")
        building = entity_record("SPACE_BUILDING", "Building")
        abstraction = entity_record("SPACE_IMPORTED", "Imported abstraction")
        node = entity_record("NODE_A", "Node A", position=[4.0, 2.0, 1.0])
        site["coordinate_space_ref"] = "SPACE_WORLD"
        building["coordinate_space_ref"] = "SPACE_SITE"
        abstraction["coordinate_space_ref"] = "SPACE_BUILDING"
        node["coordinate_space_ref"] = "SPACE_IMPORTED"
        validate_spatial_entities([world, site, building, abstraction, node])

    def test_workspace_validation_enforces_spatial_contract(self):
        workspace = starting_workspace()
        space = entity_record("SPACE_SITE", "Site space")
        node = entity_record("NODE_SPATIAL", "Spatial node", position=[1.0, 2.0, 3.0])
        node["coordinate_space_ref"] = "SPACE_SITE"
        workspace["entities"].extend([space, node])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.json"
            store = WorkspaceStore(str(path))
            saved = store.save(copy.deepcopy(workspace))
            restored = store.load()
        restored_node = next(entity for entity in restored["entities"] if entity["id"] == "NODE_SPATIAL")
        self.assertEqual(restored_node["coordinate_space_ref"], "SPACE_SITE")
        self.assertEqual(restored_node["position"], [1.0, 2.0, 3.0])
        self.assertEqual(saved, restored)


if __name__ == "__main__":
    unittest.main()
