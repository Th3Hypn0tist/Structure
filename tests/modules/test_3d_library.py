from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"
LIB = STATIC / "3d"


class ThreeDLibraryTests(unittest.TestCase):
    def test_generic_object_library_exists(self):
        expected = (
            "core.js",
            "math.js",
            "objects/object.js",
            "objects/primitives.js",
            "objects/anchors.js",
            "objects/links.js",
            "objects/props.js",
            "objects/props_item.js",
            "objects/events.js",
            "objects/event_item.js",
            "objects/pulse.js",
            "objects/highlight.js",
        )
        for name in expected:
            with self.subTest(name=name):
                self.assertTrue((LIB / name).is_file())

    def test_library_does_not_own_structure_canonical_semantics(self):
        source = "\n".join(path.read_text(encoding="utf-8") for path in LIB.rglob("*.js"))
        forbidden = (
            "property_type_ref",
            "ruleset_ref",
            "link_type_ref",
            "canonicalIndex",
            "assertWorkspace",
            "StructurePlayback",
            "StructureCausalProjection",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, source)

    def test_anchor_and_link_are_generic_object_mechanics(self):
        anchors = (LIB / "objects" / "anchors.js").read_text(encoding="utf-8")
        links = (LIB / "objects" / "links.js").read_text(encoding="utf-8")
        self.assertIn("class Anchor", anchors)
        self.assertIn("worldPosition()", anchors)
        self.assertIn("class Link", links)
        self.assertIn("from instanceof S3D.Anchor", links)
        self.assertIn("to instanceof S3D.Anchor", links)
        self.assertIn("pointAt", links)

    def test_props_and_events_are_instantiable_object_groups(self):
        props = (LIB / "objects" / "props.js").read_text(encoding="utf-8")
        events = (LIB / "objects" / "events.js").read_text(encoding="utf-8")
        self.assertIn("class Props extends S3D.Group", props)
        self.assertIn("class Events extends S3D.Group", events)
        self.assertIn("addItem", props)
        self.assertIn("addItem", events)

    def test_structure_playback_uses_library_instance(self):
        adapter = (STATIC / "playback_runtime.js").read_text(encoding="utf-8")
        self.assertIn("new window.S3D.Playback", adapter)
        self.assertIn("clock: playbackClock", adapter)
        self.assertIn("playbackClock.step()", adapter)
        self.assertNotIn("manualAdvanceMs += next - current", adapter)


if __name__ == "__main__":
    unittest.main()
