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
            "renderer.js",
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

    def test_props_and_events_are_instantiable_drawable_object_groups(self):
        props = (LIB / "objects" / "props.js").read_text(encoding="utf-8")
        props_item = (LIB / "objects" / "props_item.js").read_text(encoding="utf-8")
        events = (LIB / "objects" / "events.js").read_text(encoding="utf-8")
        event_item = (LIB / "objects" / "event_item.js").read_text(encoding="utf-8")
        self.assertIn("class Props extends S3D.Group", props)
        self.assertIn("class Events extends S3D.Group", events)
        self.assertIn("addItem", props)
        self.assertIn("addItem", events)
        self.assertIn("renderer?.box", props_item)
        self.assertIn("renderer?.box", event_item)

    def test_structure_playback_uses_library_instance(self):
        adapter = (STATIC / "playback_runtime.js").read_text(encoding="utf-8")
        self.assertIn("new window.S3D.Playback", adapter)
        self.assertIn("clock: playbackClock", adapter)
        self.assertIn("playbackClock.step()", adapter)
        self.assertNotIn("manualAdvanceMs += next - current", adapter)

    def test_structure_adapter_instantiates_events_props_anchors_and_links(self):
        adapter = (STATIC / "structure_s3d_adapter.js").read_text(encoding="utf-8")
        for token in (
            "new S3D.SceneObject",
            "new S3D.Events",
            "new S3D.EventItem",
            "new S3D.Props",
            "new S3D.PropsItem",
            "new S3D.Anchor",
            "new S3D.Link",
            "new S3D.Pulse",
        ):
            with self.subTest(token=token):
                self.assertIn(token, adapter)
        self.assertIn("drawSceneProjection3D = function drawSceneProjectionViaS3D", adapter)
        self.assertIn("drawGenericLinks3D = function drawGenericLinksViaS3D", adapter)

    def test_structure_semantics_stay_outside_library_boundary(self):
        adapter = (STATIC / "structure_s3d_adapter.js").read_text(encoding="utf-8")
        library = "\n".join(path.read_text(encoding="utf-8") for path in LIB.rglob("*.js"))
        self.assertIn("propertyDisplayName", adapter)
        self.assertIn("activeLinkProperties", adapter)
        self.assertNotIn("propertyDisplayName", library)
        self.assertNotIn("activeLinkProperties", library)

    def test_dynamic_adapter_assets_are_served(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        playback = (STATIC / "playback_runtime.js").read_text(encoding="utf-8")
        for path in ("/static/3d/renderer.js", "/static/structure_s3d_adapter.js"):
            self.assertIn(path, app)
            self.assertIn(path, playback)


if __name__ == "__main__":
    unittest.main()
