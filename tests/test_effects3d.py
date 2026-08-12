from __future__ import annotations

import unittest

from effects3d import apply_effects, manifest


class Universal3DEffectsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.canonical_like = {
            "id": "test.canonical.3d",
            "dimension": "3d",
            "kind": "flow3d",
            "nodes": [
                {"id": "a", "name": "A", "x": -10.0, "y": 0.0, "z": 0.0, "status": "locked"},
                {"id": "b", "name": "B", "x": 10.0, "y": 20.0, "z": 5.0, "status": "unlocked"},
            ],
            "edges": [{"id": "ab", "dimension": "dependencies", "source": "a", "target": "b"}],
            "groups": [],
            "extent": 100.0,
        }
        self.raw_like = {
            "id": "raw_json_space_3d",
            "dimension": "3d",
            "kind": "raw_json_space",
            "nodes": [
                {"id": "raw:/#", "name": "/", "x": 0.0, "y": 0.0, "z": 0.0},
                {"id": "raw:/#/a", "name": "a", "x": 20.0, "y": -20.0, "z": 0.0},
            ],
            "edges": [{"id": "contains", "dimension": "containment", "source": "raw:/#", "target": "raw:/#/a"}],
            "groups": [],
            "extent": 100.0,
        }

    def test_library_groups_exist(self) -> None:
        groups = {group["id"] for group in manifest()["groups"]}
        self.assertTrue({"minimal", "technical", "neon", "debug"}.issubset(groups))

    def test_same_library_applies_to_canonical_and_raw(self) -> None:
        params = {"extrusion": 82, "glow": 1.05, "scale_x": 1.5}
        canonical = apply_effects(self.canonical_like, params)
        raw = apply_effects(self.raw_like, params)
        self.assertEqual(canonical["style"]["extrusion"], 82)
        self.assertEqual(raw["style"]["extrusion"], 82)
        self.assertEqual(canonical["style"]["glow"], 1.05)
        self.assertEqual(raw["style"]["glow"], 1.05)

    def test_effects_do_not_change_semantic_identity_or_edges(self) -> None:
        projected = apply_effects(self.canonical_like, {"scale_x": 2.0, "extrusion": 80})
        self.assertEqual([n["id"] for n in projected["nodes"]], ["a", "b"])
        self.assertEqual(projected["edges"], self.canonical_like["edges"])
        self.assertEqual(projected["nodes"][0]["x"], -20.0)
        self.assertEqual(projected["nodes"][1]["x"], 20.0)

    def test_library_exposes_environment_and_lighting_controls(self) -> None:
        controls = {c["id"] for c in manifest()["groups"][0]["controls"]}
        all_controls = {c["id"] for group in manifest()["groups"] for c in group["controls"]}
        self.assertIn("scene_glow", all_controls)
        self.assertIn("vignette", all_controls)
        self.assertIn("depth_shadow", all_controls)
        self.assertIn("face_contrast", all_controls)


if __name__ == "__main__":
    unittest.main()
